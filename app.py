from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("ATTESTATION_DB", ROOT / "attestation.sqlite3"))
META_VERIFY_URL = os.environ.get(
    "META_VERIFY_URL", "https://graph.oculus.com/platform_integrity/verify"
)
CHALLENGE_TTL = int(os.environ.get("CHALLENGE_TTL_SECONDS", "300"))
MAX_TOKEN_AGE = int(os.environ.get("META_MAX_TOKEN_AGE_SECONDS", "600"))
HTTP_TIMEOUT = float(os.environ.get("META_HTTP_TIMEOUT_SECONDS", "15"))

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextmanager
def db_session():
    conn = db_connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_session() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS challenges (
                challenge_id TEXT PRIMARY KEY,
                nonce TEXT NOT NULL UNIQUE,
                package_id TEXT NOT NULL,
                session_ref TEXT NOT NULL,
                studio_id TEXT NOT NULL DEFAULT 'default',
                device_serial TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                used_at INTEGER
            )
        """)
        # Migrate existing deployments without discarding outstanding challenge history.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(challenges)")}
        if "studio_id" not in columns:
            conn.execute("ALTER TABLE challenges ADD COLUMN studio_id TEXT NOT NULL DEFAULT 'default'")
        if "device_serial" not in columns:
            conn.execute("ALTER TABLE challenges ADD COLUMN device_serial TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_challenges_expiry ON challenges(expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_challenges_studio ON challenges(studio_id, device_serial)")


init_db()


def error(message: str, status: int = 400, **extra):
    return jsonify({"ok": False, "error": message, **extra}), status


def b64url_decode_json(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        raise ValueError("Missing encoded claims")
    raw = value.encode("ascii")
    raw += b"=" * (-len(raw) % 4)
    decoded = base64.urlsafe_b64decode(raw)
    obj = json.loads(decoded.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Claims were not a JSON object")
    return obj


def _normalise_certs(values: Any) -> set[str]:
    if isinstance(values, str):
        values = values.replace("\\n", ",").split(",")
    if not isinstance(values, list):
        return set()
    certs = {re.sub(r"[^0-9a-f]", "", str(item).lower()) for item in values if str(item).strip()}
    return {cert for cert in certs if len(cert) == 64}


def load_studios() -> dict[str, dict[str, Any]]:
    """Load private per-studio Meta configuration from STUDIO_PROFILES_JSON.

    Expected format: a JSON array of objects with id, name, package_id,
    access_token, allowed_cert_sha256 and allowed_device_serials.
    """
    raw = os.environ.get("STUDIO_PROFILES_JSON", "").strip()
    if raw:
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as exc:
            app.logger.error("STUDIO_PROFILES_JSON is invalid JSON: %s", exc)
            return {}
        if not isinstance(entries, list):
            app.logger.error("STUDIO_PROFILES_JSON must be a JSON array")
            return {}
        profiles: dict[str, dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            studio_id = str(entry.get("id", "")).strip()
            name = str(entry.get("name", "")).strip()
            package_id = str(entry.get("package_id", "")).strip()
            access_token = str(entry.get("access_token", "")).strip()
            certs = _normalise_certs(entry.get("allowed_cert_sha256", []))
            serials_raw = entry.get("allowed_device_serials", [])
            serials = {str(value).strip() for value in serials_raw if str(value).strip()} if isinstance(serials_raw, list) else set()
            if (not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", studio_id)
                    or not name or len(name) > 100
                    or not re.fullmatch(r"[A-Za-z0-9_]+(\\.[A-Za-z0-9_]+)+", package_id)
                    or not access_token or not certs or not serials):
                app.logger.warning("Skipping incomplete or invalid studio profile: %s", studio_id or "(no id)")
                continue
            profiles[studio_id] = {
                "id": studio_id, "name": name, "package_id": package_id,
                "access_token": access_token, "certs": certs, "serials": serials,
            }
        return profiles

    # Backwards-compatible single-studio setup. A serial allow-list is still required.
    access_token = os.environ.get("META_APP_ACCESS_TOKEN", "").strip()
    package_id = os.environ.get("META_PACKAGE_ID", "").strip()
    certs = _normalise_certs(os.environ.get("META_ALLOWED_CERT_SHA256", ""))
    serials = {item.strip() for item in os.environ.get("META_ALLOWED_DEVICE_SERIALS", "").split(",") if item.strip()}
    if access_token and package_id and certs and serials:
        return {"default": {
            "id": "default", "name": os.environ.get("META_STUDIO_NAME", "Default Studio").strip(),
            "package_id": package_id, "access_token": access_token,
            "certs": certs, "serials": serials,
        }}
    return {}


def configured_meta() -> tuple[str, str, set[str]]:
    profiles = load_studios()
    if len(profiles) == 1:
        profile = next(iter(profiles.values()))
        return profile["access_token"], profile["package_id"], profile["certs"]
    return "", "", set()



@app.get("/")
def home():
    return send_from_directory(ROOT, "index.html")


@app.get("/style.css")
def stylesheet():
    return send_from_directory(ROOT, "style.css")


@app.get("/app.js")
def javascript():
    return send_from_directory(ROOT, "app.js")


@app.get("/health")
@app.get("/api/health")
def health():
    profiles = load_studios()
    configured = len(profiles)
    cert_count = sum(len(profile["certs"]) for profile in profiles.values())
    return jsonify({
        "ok": True,
        "service": "Attestation Studio",
        "meta_configured": configured > 0,
        "meta": {
            "access_token_present": configured > 0,
            "package_id_present": configured > 0,
            "certificate_fingerprints_configured": cert_count,
            "studio_profiles_configured": configured,
            "verification_endpoint": META_VERIFY_URL,
        },
        "adb": {
            "mode": "local companion",
            "note": "ADB runs on a computer connected to the Quest, not inside the Render web service.",
            "agent_url_configured": bool(os.environ.get("ADB_AGENT_URL")),
        },
        "challenge_ttl_seconds": CHALLENGE_TTL,
        "server_time": int(time.time()),
    })


@app.get("/api/studios")
def public_studios():
    # Never return access tokens, certificate digests or device serials to the browser.
    profiles = load_studios()
    return jsonify({
        "ok": True,
        "studios": [{"id": p["id"], "name": p["name"]} for p in profiles.values()],
        "configured": bool(profiles),
    })


@app.get("/api/config")
def public_config():
    return jsonify({
        "challenge_ttl_seconds": CHALLENGE_TTL,
        "meta_configured": bool(load_studios()),
    })


@app.post("/api/challenge")
def create_challenge():
    data = request.get_json(silent=True) or {}
    studio_id = str(data.get("studio_id", "")).strip()
    device_serial = str(data.get("device_serial", "")).strip()
    session_ref = str(data.get("session_ref") or "studio-session").strip()
    profiles = load_studios()
    profile = profiles.get(studio_id)

    if not profile:
        return error("Choose a configured studio. No matching studio profile is available.", 422)
    if not device_serial or len(device_serial) > 128 or any(ord(ch) < 33 or ord(ch) > 126 for ch in device_serial):
        return error("Enter a valid Quest device serial number.", 400)
    if device_serial not in profile["serials"]:
        return error("This device serial is not registered to the selected studio.", 403)
    if len(session_ref) > 128:
        return error("Session reference must be 128 characters or fewer.")

    nonce = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
    challenge_id = secrets.token_urlsafe(18)
    now = int(time.time())
    expires = now + CHALLENGE_TTL

    with db_session() as conn:
        conn.execute(
            """INSERT INTO challenges
               (challenge_id, nonce, package_id, session_ref, studio_id, device_serial,
                created_at, expires_at, state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (challenge_id, nonce, profile["package_id"], session_ref, studio_id,
             device_serial, now, expires),
        )
        conn.execute("DELETE FROM challenges WHERE expires_at < ?", (now - 86400,))

    return jsonify({
        "ok": True,
        "challenge_id": challenge_id,
        "challenge_nonce": nonce,
        "studio_id": studio_id,
        "studio_name": profile["name"],
        "device_serial": device_serial,
        "package_id": profile["package_id"],
        "session_ref": session_ref,
        "created_at": now,
        "expires_at": expires,
        "expires_in": CHALLENGE_TTL,
        "nonce_length": len(nonce),
        "instructions": "Pass challenge_nonce to Meta DeviceApplicationIntegrity.getIntegrityToken() in your authorised native Quest app.",
    })


@contextmanager
def reserve_challenge(challenge_id: str, nonce: str):
    """Atomically reserve a challenge to prevent concurrent replay."""
    conn = db_connect()
    row = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM challenges WHERE challenge_id=? AND nonce=?",
            (challenge_id, nonce),
        ).fetchone()
        now = int(time.time())
        if not row or row["state"] != "pending" or row["expires_at"] < now:
            conn.rollback()
            yield None, None
            return
        conn.execute(
            "UPDATE challenges SET state='processing' WHERE challenge_id=? AND state='pending'",
            (challenge_id,),
        )
        conn.commit()
        yield dict(row), conn
    finally:
        conn.close()


def finish_challenge(challenge_id: str, success: bool):
    with db_session() as conn:
        if success:
            conn.execute(
                "UPDATE challenges SET state='used', used_at=? WHERE challenge_id=? AND state='processing'",
                (int(time.time()), challenge_id),
            )
        else:
            conn.execute(
                "UPDATE challenges SET state='pending' WHERE challenge_id=? AND state='processing'",
                (challenge_id,),
            )


def verify_with_meta(token: str, access_token: str) -> dict[str, Any]:
    response = requests.get(
        META_VERIFY_URL,
        params={"token": token, "access_token": access_token},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("Meta returned an unexpected response.")
    if body.get("error"):
        raise ValueError(str(body["error"].get("message", "Meta verification failed")))
    data = body.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ValueError("Meta response did not contain a verification result.")
    result = data[0]
    if str(result.get("message", "")).lower() != "success":
        raise ValueError(str(result.get("message") or "Meta did not verify the token."))
    claims = b64url_decode_json(result.get("claims", ""))
    return claims


def evaluate_claims(claims: dict[str, Any], challenge: dict[str, Any], allowed_certs: set[str]) -> list[str]:
    issues: list[str] = []
    request_details = claims.get("request_details") or {}
    app_state = claims.get("app_state") or {}
    device_state = claims.get("device_state") or {}

    if not isinstance(request_details, dict) or not isinstance(app_state, dict) or not isinstance(device_state, dict):
        return ["unexpected_claim_structure"]

    claim_nonce = str(request_details.get("nonce", ""))
    if not secrets.compare_digest(claim_nonce, challenge["nonce"]):
        issues.append("nonce_mismatch")

    now = int(time.time())
    try:
        exp = int(request_details.get("exp", 0))
        issued = int(request_details.get("timestamp", 0))
        if exp <= now:
            issues.append("token_expired")
        if issued <= 0 or issued > now + 60:
            issues.append("invalid_issue_timestamp")
        elif now - issued > MAX_TOKEN_AGE:
            issues.append("token_too_old_for_this_session")
        if exp and issued and exp < issued:
            issues.append("invalid_token_time_range")
    except (TypeError, ValueError):
        issues.append("invalid_request_details_time")

    if str(app_state.get("package_id", "")) != challenge["package_id"]:
        issues.append("package_id_mismatch")
    if app_state.get("app_integrity_state") != "StoreRecognized":
        issues.append("app_not_store_recognized")

    claim_certs = app_state.get("package_cert_sha256_digest") or []
    normalized_claim_certs = {
        re.sub(r"[^0-9a-f]", "", str(value).lower())
        for value in claim_certs
    } if isinstance(claim_certs, list) else set()
    if not allowed_certs.intersection(normalized_claim_certs):
        issues.append("certificate_digest_mismatch")

    device_integrity = device_state.get("device_integrity_state")
    accepted = {v.strip() for v in os.environ.get("META_ACCEPTED_DEVICE_STATES", "Advanced,Basic").split(",") if v.strip()}
    if device_integrity not in accepted:
        issues.append("device_integrity_not_accepted")

    device_ban = claims.get("device_ban") or {}
    if isinstance(device_ban, dict) and device_ban.get("is_banned") is True:
        issues.append("device_is_banned")

    return issues


@app.post("/api/verify/meta")
def verify_meta():
    data = request.get_json(silent=True) or {}
    challenge_id = str(data.get("challenge_id", "")).strip()
    nonce = str(data.get("challenge_nonce", "")).strip()
    token = str(data.get("attestation_token", "")).strip()

    if not challenge_id or not nonce or not token:
        return error("challenge_id, challenge_nonce and attestation_token are required.")
    if len(token) > 24000:
        return error("Attestation token exceeds the 24 KB request limit.")

    with reserve_challenge(challenge_id, nonce) as (challenge, _):
        if not challenge:
            return error("Challenge is invalid, expired, already processing, or already used.", 409)

        profile = load_studios().get(challenge["studio_id"])
        if not profile or challenge["device_serial"] not in profile["serials"]:
            finish_challenge(challenge_id, False)
            return error("Studio profile or device registration is no longer valid.", 403)
        if challenge["package_id"] != profile["package_id"]:
            finish_challenge(challenge_id, False)
            return error("Challenge package does not match the selected studio profile.", 422)

        try:
            claims = verify_with_meta(token, profile["access_token"])
        except requests.Timeout:
            finish_challenge(challenge_id, False)
            return error("Meta verification timed out. The challenge remains reusable until expiry.", 504)
        except requests.RequestException:
            app.logger.exception("Meta verification network error")
            finish_challenge(challenge_id, False)
            return error("Could not reach Meta verification. Check the server network and try again.", 502)
        except (ValueError, json.JSONDecodeError) as exc:
            finish_challenge(challenge_id, False)
            return error(f"Meta verification failed: {exc}", 401)

        issues = evaluate_claims(claims, challenge, profile["certs"])
        finish_challenge(challenge_id, True)
        return jsonify({
            "ok": not issues,
            "provider_verified": True,
            "policy_passed": not issues,
            "provider": "Meta Platform Attestation",
            "studio_id": challenge["studio_id"],
            "studio_name": profile["name"],
            "device_serial": challenge["device_serial"],
            "package_id": claims.get("app_state", {}).get("package_id"),
            "app_integrity_state": claims.get("app_state", {}).get("app_integrity_state"),
            "device_integrity_state": claims.get("device_state", {}).get("device_integrity_state"),
            "issued_at": (claims.get("request_details") or {}).get("timestamp"),
            "expires_at": (claims.get("request_details") or {}).get("exp"),
            "policy_issues": issues,
            "claims": claims,
            "challenge_consumed": True,
        }), (200 if not issues else 422)


@app.get("/api/adb/status")
def adb_status():
    agent = os.environ.get("ADB_AGENT_URL", "").rstrip("/")
    if not agent:
        return jsonify({
            "ok": True, "available": False, "mode": "local-companion",
            "message": "No ADB companion configured. Run adb_agent.py on the computer connected to the Quest.",
        })
    try:
        r = requests.get(agent + "/health", timeout=3)
        r.raise_for_status()
        return jsonify({"ok": True, "available": True, "agent": r.json()})
    except requests.RequestException:
        return jsonify({"ok": True, "available": False, "message": "Configured ADB companion is offline."})


@app.get("/api/adb/devices")
def adb_devices_proxy():
    agent = os.environ.get("ADB_AGENT_URL", "").rstrip("/")
    secret = os.environ.get("ADB_AGENT_TOKEN", "")
    if not agent:
        return error("ADB companion is not configured. ADB must run on a computer on the Quest's network.", 503)
    try:
        r = requests.get(agent + "/api/devices", headers={"X-Agent-Token": secret}, timeout=8)
        return (r.content, r.status_code, {"Content-Type": "application/json"})
    except requests.RequestException:
        return error("ADB companion is offline.", 502)


@app.errorhandler(413)
def too_large(_):
    return error("Request too large.", 413)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
