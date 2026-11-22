import os
import re
import time
import uuid
import secrets
import threading

import jwt
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

# Set this in Render Environment Variables. Keep it stable across deployments.
SECRET = os.environ.get("ATTESTATION_SECRET")
if not SECRET:
    SECRET = secrets.token_urlsafe(48)
    app.logger.warning(
        "ATTESTATION_SECRET is not configured; tokens will stop verifying after restart."
    )

ISSUER = "https://local-attestation.example"
ALGORITHM = "HS256"
CHALLENGE_TTL = 120

# Demo-only in-memory challenge store. Use Redis or a database for multi-worker production.
challenges = {}
challenge_lock = threading.Lock()


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/challenge")
def create_challenge():
    nonce = secrets.token_hex(16)
    now = int(time.time())
    with challenge_lock:
        challenges[nonce] = now + CHALLENGE_TTL
    return jsonify({"nonce": nonce, "expires_in": CHALLENGE_TTL})


def profile_times(profile, now):
    if profile == "active":
        return now, now + 86400, "ACTIVE"
    if profile == "expired":
        return now - 86400, now - 300, "EXPIRED"
    if profile == "revoked":
        return now, now + 86400, "REVOKED"
    raise ValueError("Unknown profile")


def valid_fingerprint(value):
    if not isinstance(value, str):
        return False
    parts = value.split(":")
    return (
        len(parts) == 32
        and all(re.fullmatch(r"[0-9A-Fa-f]{2}", part) for part in parts)
    )


@app.post("/api/generate")
def generate_token():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode")
    profile = data.get("profile")
    nonce = data.get("nonce")
    now = int(time.time())

    if mode not in ("standard", "meta"):
        return jsonify({"error": "Invalid engine"}), 400
    if profile not in ("active", "expired", "revoked"):
        return jsonify({"error": "Invalid profile"}), 400
    if not isinstance(nonce, str) or not nonce or len(nonce) > 512:
        return jsonify({"error": "Invalid nonce"}), 400

    try:
        issued, expiry, status = profile_times(profile, now)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if mode == "standard":
        with challenge_lock:
            challenge_expiry = challenges.pop(nonce, None)
        if challenge_expiry is None or now > challenge_expiry:
            return jsonify({"error": "Challenge invalid, expired, or already used"}), 400

        device = data.get("device", "test-device")
        if not isinstance(device, str) or not device or len(device) > 128:
            return jsonify({"error": "Invalid device identifier"}), 400

        payload = {
            "iss": ISSUER,
            "sub": device,
            "jti": "tok-" + uuid.uuid4().hex,
            "iat": issued,
            "exp": expiry,
            "nonce": nonce,
            "appLicensingVerdict": "MOCK_LICENSED" if profile == "active" else "UNVERIFIED",
            "integrityVerdict": {
                "deviceIntegrity": ["MOCK_DEVICE_INTEGRITY"] if profile == "active" else []
            },
            "status": status,
            "environment": "LOCAL_SIMULATION",
        }
        if profile == "revoked":
            payload["reason"] = "SIMULATED_KEY_COMPROMISE"

    else:
        package = data.get("package_name")
        certificate = data.get("certificate_sha256")

        if not isinstance(package, str) or not package or len(package) > 255:
            return jsonify({"error": "Invalid package name"}), 400
        if not valid_fingerprint(certificate):
            return jsonify({"error": "Certificate must be a 32-byte colon-separated SHA-256 fingerprint"}), 400

        device_integrity = "Advanced" if profile == "active" else "None"
        app_integrity = "Recognized" if profile == "active" else "Unrecognized"

        if profile == "revoked":
            # A deliberately simulated mismatch, not provider-issued evidence.
            certificate = "FF:EE:DD:CC:BB:AA:00:99:88:77:66:55:44:33:22:11:FE:DC:BA:98:76:54:32:10:00:11:22:33:44:55:66:77"

        payload = {
            # Local issuer is intentional: this is not a Meta-issued attestation.
            "iss": ISSUER,
            "iat": issued,
            "exp": expiry,
            "nonce": nonce,
            "package_name": package,
            "certificate_sha256": certificate,
            "device_integrity": device_integrity,
            "app_integrity": app_integrity,
            "status": status,
            "environment": "LOCAL_SIMULATION",
        }
        if profile == "revoked":
            payload["reason"] = "SIMULATED_INTEGRITY_FAILURE"

    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    return jsonify({
        "success": True,
        "mode": mode,
        "profile": profile,
        "token": token,
        "payload": payload,
        "signature_type": "LOCAL_HS256",
        "provider_verified": False,
    })


@app.post("/api/verify")
def verify_token():
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    if not isinstance(token, str) or not token:
        return jsonify({"valid": False, "error": "Missing token"}), 400

    try:
        payload = jwt.decode(
            token,
            SECRET,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["iss", "iat", "exp", "nonce", "status"]},
        )
        if payload.get("status") != "ACTIVE":
            return jsonify({
                "valid": False,
                "signature_valid": True,
                "error": "Token is not an active profile",
                "payload": payload,
                "provider_verified": False,
            }), 200

        return jsonify({
            "valid": True,
            "signature_valid": True,
            "provider_verified": False,
            "payload": payload,
        })
    except jwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "Token expired"}), 401
    except jwt.InvalidTokenError as exc:
        return jsonify({"valid": False, "error": str(exc)}), 401


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
