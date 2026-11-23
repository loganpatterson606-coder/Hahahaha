import os, re, json, time, secrets, hashlib, sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory, g
import requests

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ATTESTATION_DB", os.path.join(APP_DIR, "attestation.sqlite3"))
META_VERIFY_URL = os.environ.get("META_VERIFY_URL", "https://graph.oculus.com/platform_integrity/verify")
CHALLENGE_TTL = int(os.environ.get("CHALLENGE_TTL_SECONDS", "300"))
META_MAX_AGE = int(os.environ.get("META_MAX_AGE_SECONDS", "300"))

app = Flask(__name__, static_folder=None)
app.config["JSON_SORT_KEYS"] = False

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS challenges (
            id TEXT PRIMARY KEY, nonce TEXT NOT NULL, session_tag TEXT NOT NULL,
            created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
            consumed_at INTEGER
        )""")
        conn.commit()

def json_error(message, status=400):
    return jsonify({"ok": False, "error": message}), status

@app.get("/")
def index():
    return send_from_directory(APP_DIR, "index.html")

@app.get("/style.css")
def stylesheet():
    return send_from_directory(APP_DIR, "style.css")

@app.get("/health")
def health():
    configured = all(os.environ.get(k) for k in (
        "META_APP_ACCESS_TOKEN", "META_PACKAGE_ID", "META_ALLOWED_CERT_SHA256"
    ))
    return jsonify({
        "ok": True,
        "service": "Attestation Studio",
        "meta_server_configured": configured,
        "challenge_ttl_seconds": CHALLENGE_TTL
    })

@app.post("/api/challenge")
def create_challenge():
    body = request.get_json(silent=True) or {}
    session_tag = str(body.get("session_tag", "")).strip()
    if not session_tag or len(session_tag) > 200:
        return json_error("Provide a session_tag (1–200 characters).")
    challenge_id = secrets.token_urlsafe(18)
    nonce = secrets.token_urlsafe(32)
    now = int(time.time())
    expires = now + CHALLENGE_TTL
    db().execute(
        "INSERT INTO challenges(id, nonce, session_tag, created_at, expires_at) VALUES(?,?,?,?,?)",
        (challenge_id, nonce, session_tag, now, expires)
    )
    db().commit()
    return jsonify({
        "ok": True, "challenge_id": challenge_id, "nonce": nonce,
        "expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat()
    })

def consume_challenge(challenge_id, nonce):
    now = int(time.time())
    conn = db()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT * FROM challenges WHERE id=? AND nonce=?",
        (challenge_id, nonce)
    ).fetchone()
    if not row or row["consumed_at"] is not None or row["expires_at"] < now:
        conn.rollback()
        return None
    conn.execute("UPDATE challenges SET consumed_at=? WHERE id=? AND consumed_at IS NULL",
                 (now, challenge_id))
    if conn.total_changes < 1:
        conn.rollback()
        return None
    conn.commit()
    return dict(row)

def decode_claims_for_policy(token):
    # This only decodes the payload for policy inspection. It does NOT verify
    # the signature. Signature/provider verification is performed by Meta below.
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    except Exception:
        return None

@app.post("/api/verify/meta")
def verify_meta():
    body = request.get_json(silent=True) or {}
    challenge_id = str(body.get("challenge_id", "")).strip()
    nonce = str(body.get("nonce", "")).strip()
    token = str(body.get("token", "")).strip()
    if not all((challenge_id, nonce, token)):
        return json_error("challenge_id, nonce, and provider-issued token are required.")
    if len(token) > 20000:
        return json_error("Token is too large.")
    access_token = os.environ.get("META_APP_ACCESS_TOKEN")
    package_id = os.environ.get("META_PACKAGE_ID")
    cert_hash = os.environ.get("META_ALLOWED_CERT_SHA256", "").replace(":", "").lower()
    if not all((access_token, package_id, cert_hash)):
        return json_error("Server is not configured. Set META_APP_ACCESS_TOKEN, META_PACKAGE_ID, and META_ALLOWED_CERT_SHA256.", 503)

    challenge = consume_challenge(challenge_id, nonce)
    if not challenge:
        return json_error("Challenge is invalid, expired, or already used.", 409)

    try:
        response = requests.get(
            META_VERIFY_URL,
            params={"token": token, "access_token": access_token},
            timeout=12
        )
        response.raise_for_status()
        provider_data = response.json()
    except requests.RequestException:
        app.logger.exception("Meta verification request failed")
        return json_error("Meta verification service could not be reached.", 502)
    except ValueError:
        return json_error("Meta returned an unreadable response.", 502)

    # Provider response formats can vary by API version. Do not infer success
    # from a locally decoded JWT; require an explicit successful provider result.
    if provider_data.get("error") or provider_data.get("success") is False:
        return jsonify({"ok": False, "provider_verified": False,
                        "error": "Meta did not verify this token.",
                        "provider_response": provider_data}), 401

    claims = decode_claims_for_policy(token)
    if not isinstance(claims, dict):
        return jsonify({"ok": False, "provider_verified": True,
                        "policy_passed": False,
                        "error": "Provider accepted token, but claims could not be decoded."}), 422

    # Claim names and response shape must be checked against the current Meta
    # Platform Integrity documentation for the app's SDK/API version.
    problems = []
    token_nonce = str(claims.get("nonce", ""))
    if token_nonce and not secrets.compare_digest(token_nonce, nonce):
        problems.append("nonce_mismatch")
    exp = claims.get("exp")
    if exp is not None:
        try:
            if int(exp) < int(time.time()):
                problems.append("token_expired")
        except (TypeError, ValueError):
            problems.append("invalid_exp")
    if claims.get("package_id") and str(claims["package_id"]) != package_id:
        problems.append("package_id_mismatch")
    if claims.get("app_integrity_state") and claims["app_integrity_state"] != "StoreRecognized":
        problems.append("app_integrity_not_store_recognized")
    if claims.get("certificate_sha256") and str(claims["certificate_sha256"]).replace(":", "").lower() != cert_hash:
        problems.append("certificate_mismatch")

    return jsonify({
        "ok": not problems,
        "provider_verified": True,
        "policy_passed": not problems,
        "policy_issues": problems,
        "session_tag": challenge["session_tag"],
        "note": "Review the claim mapping against the current Meta API response for your app before production use."
    }), (200 if not problems else 422)

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)

# Ensure schema exists when deployed under a WSGI server.
init_db()
