import base64
import hashlib
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, jsonify, request, render_template, Response

app = Flask(__name__)
ISSUERS = {
    "standard": "https://local-attestation.example/standard",
    "meta": "https://local-attestation.example/meta-simulation",
}
ALGORITHM = "RS256"
CHALLENGE_TTL = 300
KEY_DIR = Path(os.environ.get("ATTESTATION_KEY_DIR", Path(__file__).resolve().parent / "keys"))
KEY_DIR.mkdir(parents=True, exist_ok=True)

def load_or_create_key(mode):
    env_name = f"{mode.upper()}_ATTEST_PRIVATE_KEY"
    pem = os.environ.get(env_name)
    if pem:
        key = serialization.load_pem_private_key(pem.replace("\\n", "\n").encode(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise RuntimeError(f"{env_name} must contain an RSA private key")
        return key
    path = KEY_DIR / f"{mode}_rsa_private.pem"
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key

PRIVATE_KEYS = {m: load_or_create_key(m) for m in ("standard", "meta")}
PUBLIC_KEYS = {m: k.public_key() for m, k in PRIVATE_KEYS.items()}

def key_id(key):
    der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return "local-" + hashlib.sha256(der).hexdigest()[:20]

KIDS = {m: key_id(k) for m, k in PUBLIC_KEYS.items()}
challenges = {}
challenge_lock = threading.Lock()
revoked_jtis = set()
revocation_lock = threading.Lock()

def b64url_uint(value):
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

def public_jwk(mode):
    n = PUBLIC_KEYS[mode].public_numbers()
    return {"kty": "RSA", "use": "sig", "alg": ALGORITHM, "kid": KIDS[mode],
            "n": b64url_uint(n.n), "e": b64url_uint(n.e)}

def valid_fingerprint(value):
    return isinstance(value, str) and bool(re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}", value))

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify({"status": "online", "signing": "local-rs256", "modes": ["standard", "meta"]})

@app.get("/api/challenge")
def create_challenge():
    nonce = secrets.token_urlsafe(32)
    with challenge_lock:
        challenges[nonce] = int(time.time()) + CHALLENGE_TTL
    return jsonify({"success": True, "nonce": nonce, "challenge": nonce, "expires_in": CHALLENGE_TTL})

@app.get("/api/jwks.json")
def jwks():
    return jsonify({"keys": [public_jwk("standard"), public_jwk("meta")]})

@app.get("/api/keys/<mode>")
def mode_jwks(mode):
    if mode not in PUBLIC_KEYS:
        return jsonify({"error": "Unknown signing mode"}), 404
    return jsonify({"keys": [public_jwk(mode)]})

@app.get("/api/keys/<mode>.pem")
def mode_pem(mode):
    if mode not in PUBLIC_KEYS:
        return jsonify({"error": "Unknown signing mode"}), 404
    pem = PUBLIC_KEYS[mode].public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return Response(pem, mimetype="application/x-pem-file",
                    headers={"Content-Disposition": f'attachment; filename="{mode}-public.pem"'})

def profile_times(profile, now):
    if profile == "active":
        return now, now + 3600, "ACTIVE"
    if profile == "expired":
        return now - 3600, now - 60, "EXPIRED"
    if profile == "revoked":
        return now, now + 3600, "REVOKED"
    raise ValueError("Unknown profile")

@app.post("/api/generate")
def generate_token():
    data = request.get_json(silent=True) or {}
    mode, profile = data.get("mode"), data.get("profile", "active")
    nonce = data.get("nonce") or data.get("challenge")
    now = int(time.time())
    if mode not in PRIVATE_KEYS:
        return jsonify({"success": False, "error": "Invalid engine"}), 400
    if profile not in ("active", "expired", "revoked"):
        return jsonify({"success": False, "error": "Invalid profile"}), 400
    if not isinstance(nonce, str) or not nonce or len(nonce) > 512:
        return jsonify({"success": False, "error": "A nonce is required"}), 400

    issued, expiry, status = profile_times(profile, now)
    if mode == "standard":
        with challenge_lock:
            challenge_expiry = challenges.pop(nonce, None)
        if challenge_expiry is None or now > challenge_expiry:
            return jsonify({"success": False, "error": "Challenge invalid, expired, or already used"}), 400
        device = data.get("device", "test-device")
        if not isinstance(device, str) or not device or len(device) > 128:
            return jsonify({"success": False, "error": "Invalid device identifier"}), 400
        payload = {
            "iss": ISSUERS[mode], "sub": device,
            "aud": data.get("audience", "local-attestation-test-client"),
            "jti": "std-" + uuid.uuid4().hex, "iat": issued, "exp": expiry,
            "nonce": nonce,
            "appLicensingVerdict": "MOCK_LICENSED" if profile == "active" else "UNVERIFIED",
            "integrityVerdict": {"deviceIntegrity": ["LOCAL_TEST_DEVICE_INTEGRITY"] if profile == "active" else []},
            "status": status, "environment": "LOCAL_SIMULATION", "provider_verified": False,
        }
    else:
        package, certificate = data.get("package_name"), data.get("certificate_sha256")
        if not isinstance(package, str) or not package or len(package) > 255:
            return jsonify({"success": False, "error": "Invalid package name"}), 400
        if not valid_fingerprint(certificate):
            return jsonify({"success": False, "error": "Certificate must be a 32-byte colon-separated SHA-256 fingerprint"}), 400
        payload = {
            "iss": ISSUERS[mode], "sub": package,
            "aud": data.get("audience", "local-meta-style-test-client"),
            "jti": "meta-" + uuid.uuid4().hex, "iat": issued, "exp": expiry,
            "nonce": nonce, "app_id": package, "package_name": package,
            "certificate_sha256": certificate.upper(),
            "device_integrity": "Advanced" if profile == "active" else "None",
            "app_integrity": "Recognized" if profile == "active" else "Unrecognized",
            "status": status, "environment": "LOCAL_META_STYLE_SIMULATION",
            "provider_verified": False,
        }

    token = jwt.encode(payload, PRIVATE_KEYS[mode], algorithm=ALGORITHM,
                       headers={"kid": KIDS[mode], "typ": "JWT"})
    if profile == "revoked":
        with revocation_lock:
            revoked_jtis.add(payload["jti"])
    return jsonify({
        "success": True, "mode": mode, "profile": profile, "token": token, "payload": payload,
        "signature": {"algorithm": ALGORITHM, "kid": KIDS[mode],
                      "type": f"LOCAL_{mode.upper()}_RSA_SHA256",
                      "provider_verified": False, "verification_key": f"/api/keys/{mode}"},
        "provider_verified": False,
        "notice": "Cryptographically valid local test signature. Not issued or endorsed by Meta.",
    })

@app.post("/api/verify")
def verify_token():
    token = (request.get_json(silent=True) or {}).get("token")
    if not isinstance(token, str) or not token:
        return jsonify({"valid": False, "error": "Missing token"}), 400
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != ALGORITHM:
            raise jwt.InvalidAlgorithmError("Only RS256 is accepted")
        kid = header.get("kid")
        mode = next((m for m in PUBLIC_KEYS if KIDS[m] == kid), None)
        if mode is None:
            raise jwt.InvalidTokenError("Unknown signing key ID")
        payload = jwt.decode(
            token, PUBLIC_KEYS[mode], algorithms=[ALGORITHM], issuer=ISSUERS[mode],
            options={"require": ["iss", "iat", "exp", "nonce", "jti", "status"], "verify_aud": False},
        )
        with revocation_lock:
            is_revoked = payload.get("jti") in revoked_jtis
        if is_revoked or payload.get("status") == "REVOKED":
            return jsonify({"valid": False, "signature_valid": True, "revoked": True,
                            "mode": mode, "payload": payload, "provider_verified": False,
                            "error": "Signature is valid, but this local test token is revoked."})
        return jsonify({"valid": payload.get("status") == "ACTIVE", "signature_valid": True,
                        "revoked": False, "mode": mode, "algorithm": ALGORITHM, "kid": kid,
                        "payload": payload, "provider_verified": False,
                        "message": "Local RSA signature verified successfully."})
    except jwt.ExpiredSignatureError:
        # Expiry is a claims-policy failure; verify the signature separately so
        # the response accurately reports that the cryptographic signature is sound.
        try:
            header = jwt.get_unverified_header(token)
            mode = next((m for m in PUBLIC_KEYS if KIDS[m] == header.get("kid")), None)
            if mode is None or header.get("alg") != ALGORITHM:
                raise jwt.InvalidTokenError("Unknown signing key")
            expired_payload = jwt.decode(
                token, PUBLIC_KEYS[mode], algorithms=[ALGORITHM], issuer=ISSUERS[mode],
                options={"verify_exp": False, "verify_aud": False,
                         "require": ["iss", "iat", "exp", "nonce", "jti", "status"]},
            )
            return jsonify({"valid": False, "signature_valid": True, "error": "Token expired",
                            "mode": mode, "payload": expired_payload, "provider_verified": False}), 401
        except jwt.InvalidTokenError as exc:
            return jsonify({"valid": False, "signature_valid": False, "error": str(exc)}), 401
    except jwt.InvalidTokenError as exc:
        return jsonify({"valid": False, "signature_valid": False, "error": str(exc)}), 401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
