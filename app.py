"""Provider-backed attestation gateway for VR applications.

This service never creates or signs attestation tokens. It obtains provider
verdicts from Meta or Google and only returns provider_verified=True after
remote verification and local claim-policy checks succeed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder=".")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = Path(os.environ.get("ATTESTATION_INSTANCE_DIR", BASE_DIR / "instance"))
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("ATTESTATION_DB_PATH", INSTANCE_DIR / "attestation.sqlite3"))

META_VERIFY_URL = "https://graph.oculus.com/platform_integrity/verify"
GOOGLE_SCOPE = "https://www.googleapis.com/auth/playintegrity"
GOOGLE_API_BASE = "https://playintegrity.googleapis.com/v1"
CHALLENGE_TTL_SECONDS = int(os.environ.get("CHALLENGE_TTL_SECONDS", "300"))
META_MAX_TOKEN_AGE_SECONDS = int(os.environ.get("META_MAX_TOKEN_AGE_SECONDS", "300"))
GOOGLE_MAX_TOKEN_AGE_MS = int(os.environ.get("GOOGLE_MAX_TOKEN_AGE_MS", "120000"))
HTTP_TIMEOUT_SECONDS = float(os.environ.get("PROVIDER_HTTP_TIMEOUT_SECONDS", "12"))


def env_csv(name: str) -> set[str]:
    return {item.strip() for item in os.environ.get(name, "").split(",") if item.strip()}


@contextmanager
def db_connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with db_connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""
            CREATE TABLE IF NOT EXISTS challenges (
                nonce TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                action TEXT NOT NULL,
                request_hash TEXT,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_challenges_expiry ON challenges(expires_at)")


init_db()


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def decode_b64url_json(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        raise ValueError("Provider returned no claims")
    padded = value + "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Provider claims were not a JSON object")
    return parsed


def json_error(message: str, status: int = 400, **extra: Any):
    return jsonify({"success": False, "provider_verified": False, "error": message, **extra}), status


def consume_challenge(nonce: str, provider: str) -> sqlite3.Row | None:
    """Atomically consume a challenge before provider verification (replay-safe).

    A failed provider/network attempt requires a fresh challenge. This is
    intentional: the same nonce is never accepted twice.
    """
    now = int(time.time())
    with db_connect() as db:
        row = db.execute(
            "SELECT * FROM challenges WHERE nonce=? AND provider=? AND used_at IS NULL AND expires_at>?",
            (nonce, provider, now),
        ).fetchone()
        if row is None:
            return None
        updated = db.execute(
            "UPDATE challenges SET used_at=? WHERE nonce=? AND used_at IS NULL",
            (now, nonce),
        ).rowcount
        if updated != 1:
            return None
        return row


def require_string(data: dict[str, Any], key: str, max_length: int = 50000) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"'{key}' is required and must be a valid string")
    return value.strip()


def meta_configuration() -> tuple[str, str, set[str]]:
    access_token = os.environ.get("META_APP_ACCESS_TOKEN", "").strip()
    package_id = os.environ.get("META_PACKAGE_ID", "").strip()
    certs = {x.lower().replace(":", "") for x in env_csv("META_ALLOWED_CERT_SHA256")}
    missing = [name for name, value in (
        ("META_APP_ACCESS_TOKEN", access_token),
        ("META_PACKAGE_ID", package_id),
        ("META_ALLOWED_CERT_SHA256", certs),
    ) if not value]
    if missing:
        raise RuntimeError("Missing server configuration: " + ", ".join(missing))
    return access_token, package_id, certs


def verify_meta_with_provider(attestation_token: str) -> dict[str, Any]:
    access_token, _, _ = meta_configuration()
    # Meta documents this endpoint and these parameters. Credentials stay on
    # the server; never put META_APP_ACCESS_TOKEN in the VR client.
    response = requests.get(
        META_VERIFY_URL,
        params={"token": attestation_token, "access_token": access_token},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    entries = body.get("data") if isinstance(body, dict) else None
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        raise ValueError("Meta returned an unexpected verification response")
    result = entries[0]
    if result.get("message") != "success":
        reason = str(result.get("message") or "Meta rejected the attestation")
        raise ValueError("Meta verification failed: " + reason[:160])
    return decode_b64url_json(result.get("claims", ""))


def evaluate_meta_claims(claims: dict[str, Any], challenge: sqlite3.Row) -> dict[str, Any]:
    _, expected_package, allowed_certs = meta_configuration()
    now = int(time.time())
    request_details = claims.get("request_details") or {}
    app_state = claims.get("app_state") or {}
    device_state = claims.get("device_state") or {}

    if request_details.get("nonce") != challenge["nonce"]:
        raise ValueError("Meta nonce does not match the one-time server challenge")
    exp = int(request_details.get("exp", 0))
    issued = int(request_details.get("timestamp", 0))
    if exp <= now:
        raise ValueError("Meta attestation has expired")
    if exp - issued > 24 * 60 * 60 + 60:
        raise ValueError("Meta attestation lifetime is outside the documented limit")
    if issued > now + 60 or now - issued > META_MAX_TOKEN_AGE_SECONDS:
        raise ValueError("Meta attestation timestamp is not recent enough")

    package_id = app_state.get("package_id")
    if package_id != expected_package:
        raise ValueError("Attested package ID does not match META_PACKAGE_ID")
    if app_state.get("app_integrity_state") != "StoreRecognized":
        raise ValueError("Meta did not recognize this app as a Horizon Store installation")

    reported_certs = {
        str(value).lower().replace(":", "")
        for value in (app_state.get("package_cert_sha256_digest") or [])
    }
    if not reported_certs.intersection(allowed_certs):
        raise ValueError("Attested signing certificate does not match META_ALLOWED_CERT_SHA256")

    device_integrity = device_state.get("device_integrity_state")
    allowed_device_states = {"Advanced", "Basic"}
    if os.environ.get("META_ALLOW_BASIC_DEVICE", "true").lower() == "false":
        allowed_device_states = {"Advanced"}
    if device_integrity not in allowed_device_states:
        raise ValueError("Meta device integrity did not meet the configured minimum")
    if (claims.get("device_ban") or {}).get("is_banned") is True:
        raise ValueError("Meta attestation indicates this device is banned for the app")

    return {
        "provider": "meta_quest",
        "provider_verified": True,
        "valid": True,
        "package_id": package_id,
        "app_integrity_state": app_state.get("app_integrity_state"),
        "device_integrity_state": device_integrity,
        "version": app_state.get("version"),
        "expires_at": exp,
        "challenge_action": challenge["action"],
        "device_banned": False,
    }


def load_google_credentials():
    try:
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("Install google-auth to enable Google Play Integrity verification") from exc

    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    credentials_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if credentials_json:
        info = json.loads(credentials_json)
        return service_account.Credentials.from_service_account_info(info, scopes=[GOOGLE_SCOPE])
    if credentials_file:
        return service_account.Credentials.from_service_account_file(credentials_file, scopes=[GOOGLE_SCOPE])
    raise RuntimeError("Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON")


def verify_google_with_provider(integrity_token: str, package_name: str) -> dict[str, Any]:
    from google.auth.transport.requests import AuthorizedSession

    credentials = load_google_credentials()
    session = AuthorizedSession(credentials)
    url = f"{GOOGLE_API_BASE}/{package_name}:decodeIntegrityToken"
    response = session.post(
        url,
        json={"integrity_token": integrity_token},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    payload = body.get("tokenPayloadExternal")
    if not isinstance(payload, dict):
        raise ValueError("Google returned no decoded token payload")
    return payload


def evaluate_google_claims(payload: dict[str, Any], challenge: sqlite3.Row, package_name: str) -> dict[str, Any]:
    expected_package = os.environ.get("GOOGLE_PLAY_PACKAGE_NAME", "").strip()
    allowed_certs = env_csv("GOOGLE_PLAY_CERT_SHA256_B64URL")
    if not expected_package or not allowed_certs:
        raise RuntimeError("Set GOOGLE_PLAY_PACKAGE_NAME and GOOGLE_PLAY_CERT_SHA256_B64URL")
    if package_name != expected_package:
        raise ValueError("Submitted package name does not match GOOGLE_PLAY_PACKAGE_NAME")

    details = payload.get("requestDetails") or {}
    app_integrity = payload.get("appIntegrity") or {}
    device_integrity = payload.get("deviceIntegrity") or {}
    account_details = payload.get("accountDetails") or {}

    if details.get("requestPackageName") != expected_package:
        raise ValueError("Google request package name did not match")
    if details.get("requestHash") != challenge["request_hash"]:
        raise ValueError("Google requestHash does not match the one-time server challenge")
    timestamp_ms = int(details.get("timestampMillis", 0))
    now_ms = int(time.time() * 1000)
    age_ms = now_ms - timestamp_ms
    if age_ms < -30_000 or age_ms > GOOGLE_MAX_TOKEN_AGE_MS:
        raise ValueError("Google integrity response is outside the allowed freshness window")

    if app_integrity.get("appRecognitionVerdict") != "PLAY_RECOGNIZED":
        raise ValueError("Google Play did not recognize this app build")
    if app_integrity.get("packageName") != expected_package:
        raise ValueError("Google attested package name did not match")
    certs = set(app_integrity.get("certificateSha256Digest") or [])
    if not certs.intersection(allowed_certs):
        raise ValueError("Google Play signing certificate did not match configured certificate digest")

    verdicts = set(device_integrity.get("deviceRecognitionVerdict") or [])
    required_verdict = os.environ.get("GOOGLE_REQUIRED_DEVICE_VERDICT", "MEETS_DEVICE_INTEGRITY")
    if required_verdict not in verdicts:
        raise ValueError(f"Google device verdict did not include {required_verdict}")
    if os.environ.get("GOOGLE_REQUIRE_LICENSED", "true").lower() == "true":
        if account_details.get("appLicensingVerdict") != "LICENSED":
            raise ValueError("Google Play account is not licensed for this app")

    return {
        "provider": "google_play_integrity",
        "provider_verified": True,
        "valid": True,
        "package_name": expected_package,
        "app_recognition_verdict": app_integrity.get("appRecognitionVerdict"),
        "device_recognition_verdict": sorted(verdicts),
        "app_licensing_verdict": account_details.get("appLicensingVerdict"),
        "version_code": app_integrity.get("versionCode"),
        "challenge_action": challenge["action"],
        "request_timestamp_ms": timestamp_ms,
    }


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({
        "status": "online",
        "service": "vr-provider-attestation-gateway",
        "local_token_signing": False,
        "providers": {
            "meta_quest": bool(os.environ.get("META_APP_ACCESS_TOKEN") and os.environ.get("META_PACKAGE_ID") and os.environ.get("META_ALLOWED_CERT_SHA256")),
            "google_play_integrity": bool(os.environ.get("GOOGLE_PLAY_PACKAGE_NAME") and (os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")) and os.environ.get("GOOGLE_PLAY_CERT_SHA256_B64URL")),
        },
    })


@app.post("/api/challenge")
def create_challenge():
    data = request.get_json(silent=True) or {}
    provider = data.get("provider")
    action = data.get("action", "session_start")
    if provider not in ("meta_quest", "google_play_integrity"):
        return json_error("provider must be 'meta_quest' or 'google_play_integrity'")
    if not isinstance(action, str) or not action.strip() or len(action) > 100:
        return json_error("action must be a non-empty string of at most 100 characters")

    nonce = b64url(secrets.token_bytes(32))
    request_hash = None
    if provider == "google_play_integrity":
        digest_input = json.dumps({"nonce": nonce, "action": action.strip()}, sort_keys=True, separators=(",", ":")).encode()
        request_hash = b64url(hashlib.sha256(digest_input).digest())

    now = int(time.time())
    with db_connect() as db:
        db.execute("DELETE FROM challenges WHERE expires_at < ? OR used_at IS NOT NULL", (now - 3600,))
        db.execute(
            "INSERT INTO challenges(nonce,provider,action,request_hash,created_at,expires_at) VALUES(?,?,?,?,?,?)",
            (nonce, provider, action.strip(), request_hash, now, now + CHALLENGE_TTL_SECONDS),
        )
    response = {"success": True, "provider": provider, "nonce": nonce, "expires_in": CHALLENGE_TTL_SECONDS}
    if request_hash:
        response["request_hash"] = request_hash
    return jsonify(response)


@app.post("/api/verify/meta")
def verify_meta():
    data = request.get_json(silent=True) or {}
    try:
        nonce = require_string(data, "nonce", 256)
        token = require_string(data, "attestation_token", 50000)
        challenge = consume_challenge(nonce, "meta_quest")
        if challenge is None:
            return json_error("Challenge is missing, expired, already used, or belongs to another provider", 401)
        claims = verify_meta_with_provider(token)
        result = evaluate_meta_claims(claims, challenge)
        return jsonify({"success": True, **result, "claims": claims})
    except requests.RequestException:
        app.logger.exception("Meta verification service request failed")
        return json_error("Could not reach Meta verification service; request a new challenge and retry", 502)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return json_error(str(exc), 401)
    except RuntimeError as exc:
        return json_error(str(exc), 503)


@app.post("/api/verify/google")
def verify_google():
    data = request.get_json(silent=True) or {}
    try:
        nonce = require_string(data, "nonce", 256)
        token = require_string(data, "integrity_token", 50000)
        package_name = require_string(data, "package_name", 255)
        challenge = consume_challenge(nonce, "google_play_integrity")
        if challenge is None:
            return json_error("Challenge is missing, expired, already used, or belongs to another provider", 401)
        payload = verify_google_with_provider(token, package_name)
        result = evaluate_google_claims(payload, challenge, package_name)
        return jsonify({"success": True, **result, "claims": payload})
    except requests.RequestException:
        app.logger.exception("Google Play Integrity verification request failed")
        return json_error("Could not reach Google verification service; request a new challenge and retry", 502)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return json_error(str(exc), 401)
    except RuntimeError as exc:
        return json_error(str(exc), 503)


@app.errorhandler(413)
def too_large(_error):
    return json_error("Request body is too large", 413)


if __name__ == "__main__":
    # For production, run behind HTTPS with a production WSGI server (gunicorn).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
