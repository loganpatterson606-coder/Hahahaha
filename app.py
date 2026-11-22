import os
import time
import secrets
import jwt

from flask import Flask, request, jsonify, send_from_directory

# All project files can remain in the repository root.
app = Flask(__name__)

SECRET_KEY = os.environ.get("ATTESTATION_SECRET")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    app.logger.warning(
        "ATTESTATION_SECRET is not configured; local tokens will not verify after a restart."
    )

challenges = {}
revoked_tokens = set()


@app.get("/")
def home():
    return send_from_directory(".", "index.html")


@app.get("/health")
def health():
    return jsonify({"status": "online"})


@app.get("/api/challenge")
def create_challenge():
    nonce = secrets.token_urlsafe(32)
    challenges[nonce] = {"created": time.time(), "used": False}
    # Return both names for compatibility with older frontend versions.
    return jsonify({"success": True, "challenge": nonce, "nonce": nonce})


@app.post("/api/generate")
def generate_token():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "standard")
    profile = data.get("profile", "active")

    if mode not in ("standard", "meta"):
        return jsonify({"success": False, "error": "Invalid mode"}), 400
    if profile not in ("active", "expired", "revoked"):
        return jsonify({"success": False, "error": "Invalid profile"}), 400

    now = int(time.time())
    expires = now - 60 if profile == "expired" else now + 3600

    payload = {
        "iss": "https://local-attestation.example",
        "iat": now,
        "exp": expires,
        "jti": secrets.token_urlsafe(18),
        "profile": profile,
        "mode": mode,
        "provider_verified": False,
        "signature_type": "LOCAL_DEMO_HMAC_SHA256",
        "simulation": True,
    }

    if mode == "standard":
        # Accept either field name so older clients also work.
        challenge_value = data.get("challenge") or data.get("nonce")
        if not challenge_value or challenge_value not in challenges:
            return jsonify({
                "success": False,
                "error": "Generate a fresh challenge first, then generate the token."
            }), 400

        challenge = challenges[challenge_value]
        if challenge["used"]:
            return jsonify({"success": False, "error": "Challenge already used"}), 400
        if time.time() - challenge["created"] > 300:
            return jsonify({"success": False, "error": "Challenge expired; generate a new one."}), 400

        challenge["used"] = True
        payload["nonce"] = challenge_value
        payload["device_id"] = str(data.get("device") or "demo-device")[:128]

    else:
        payload.update({
            "app_id": str(data.get("package_name") or "local.demo.questapp")[:200],
            "certificate_sha256": str(data.get("certificate_sha256") or "")[:200],
            "nonce": str(data.get("nonce") or secrets.token_urlsafe(18))[:200],
            "device_integrity": "Advanced" if profile == "active" else "None",
            "app_recognition": "Recognized" if profile == "active" else "Unrecognized",
            "certificate_status": "MISMATCH" if profile == "revoked" else "MATCH",
        })

    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    if profile == "revoked":
        revoked_tokens.add(payload["jti"])

    return jsonify({
        "success": True,
        "token": token,
        "payload": payload,
        "profile": profile,
        "signature": {
            "algorithm": "HS256",
            "type": "LOCAL_DEMO_HMAC_SHA256",
            "issuer": "https://local-attestation.example",
            "provider_verified": False,
        },
        "notice": "Local development simulation only. Not issued, signed, or verified by Meta."
    })


@app.post("/api/verify")
def verify_token():
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    if not token:
        return jsonify({"valid": False, "error": "Token is required"}), 400

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("jti") in revoked_tokens:
            return jsonify({
                "valid": False,
                "error": "Token revoked in this running demo instance",
                "provider_verified": False,
            })

        return jsonify({
            "valid": True,
            "payload": payload,
            "signature_valid": True,
            "provider_verified": False,
            "message": "Local demo signature verified. This is not genuine Meta attestation.",
        })
    except jwt.ExpiredSignatureError:
        return jsonify({
            "valid": False,
            "error": "Token expired",
            "provider_verified": False,
        })
    except jwt.InvalidTokenError:
        return jsonify({
            "valid": False,
            "error": "Invalid token or signature",
            "provider_verified": False,
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
