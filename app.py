import os
import time
import secrets
import jwt

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, template_folder=".")

SECRET_KEY = os.environ.get("ATTESTATION_SECRET")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    app.logger.warning(
        "ATTESTATION_SECRET is not configured; tokens will stop verifying after restart."
    )

challenges = {}
revoked_tokens = set()


@app.route("/", methods=["GET"])
def home():
    return send_from_directory(".", "index.html")


@app.route("/api/challenge", methods=["GET"])
def create_challenge():
    nonce = secrets.token_urlsafe(32)
    challenges[nonce] = {"created": time.time(), "used": False}
    return jsonify({"success": True, "challenge": nonce})


@app.route("/api/generate", methods=["POST"])
def generate_token():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "standard")
    profile = data.get("profile", "active")

    if profile not in ("active", "expired", "revoked"):
        return jsonify({"success": False, "error": "Invalid profile"}), 400

    now = int(time.time())
    expires = now - 60 if profile == "expired" else now + 3600
    payload = {
        "iss": "https://local-attestation.example",
        "iat": now,
        "exp": expires,
        "jti": secrets.token_urlsafe(16),
        "profile": profile,
        "mode": mode,
        "provider_verified": False,
    }

    if mode == "meta":
        payload.update({
            "app_id": "local-demo-app",
            "device_integrity": "Advanced" if profile == "active" else "None",
            "app_recognition": "Recognized" if profile == "active" else "Unrecognized",
            "certificate_status": "MISMATCH" if profile == "revoked" else "MATCH",
        })
    else:
        nonce = data.get("challenge")
        if not nonce or nonce not in challenges:
            return jsonify({"success": False, "error": "A valid challenge is required"}), 400

        challenge = challenges[nonce]
        if challenge["used"]:
            return jsonify({"success": False, "error": "Challenge already used"}), 400
        if time.time() - challenge["created"] > 300:
            return jsonify({"success": False, "error": "Challenge expired"}), 400

        challenge["used"] = True
        payload["nonce"] = nonce

    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    if profile == "revoked":
        revoked_tokens.add(payload["jti"])

    return jsonify({
        "success": True,
        "token": token,
        "payload": payload,
        "profile": profile,
        "provider_verified": False,
    })


@app.route("/api/verify", methods=["POST"])
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
                "error": "Token revoked",
                "provider_verified": False,
            })

        return jsonify({
            "valid": True,
            "payload": payload,
            "provider_verified": False,
            "message": "Local signature verified. This does not establish provider attestation.",
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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "online"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
