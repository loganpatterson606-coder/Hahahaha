# Attestation Studio

A small Flask dashboard and backend starter for **your own authorised Meta Quest app**.

## What it does
- Creates a cryptographically random, short-lived, single-use challenge.
- Accepts a token produced by your native Quest application.
- Sends that token to the configured Meta verification endpoint.
- Applies a starter set of local claim checks.

## What it does not do
- It does not generate, forge, sign, or emulate Meta attestation tokens.
- A browser on its own cannot call the Quest native attestation SDK.
- It is not a token relay for third-party games or apps.

## Run locally
1. Install Python 3.10+.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Set the server-side environment variables from `.env.example`.
4. Start:
   ```bash
   python app.py
   ```
5. Open `http://127.0.0.1:5000`.

## Quest client integration
Your Unity/Unreal/native Quest client must:
1. Authenticate the user to **your own backend**.
2. Request a challenge from `POST /api/challenge` and retain both `challenge_id` and `nonce`.
3. Use the current Meta Platform Integrity SDK/API for your app to obtain a provider-issued integrity token bound to that nonce.
4. Submit `challenge_id`, `nonce`, and the token to `POST /api/verify/meta`.
5. Continue only if the backend returns `ok: true`.

The exact SDK method names and token claim schema depend on the Meta SDK/API version. Integrate against the current Meta developer documentation rather than copying guessed method names or claim fields.

## Production hardening required
This is a starter, not a production security certification:
- Put it behind HTTPS and an authenticated reverse proxy.
- Bind challenges to a server-authenticated account/session; do not trust a client-supplied `session_tag` as identity.
- Add CSRF protection where cookie authentication is used, rate limits, request-size limits, structured audit logs, and abuse monitoring.
- Use a managed secret store for Meta credentials.
- Confirm the current Meta verification endpoint, required parameters, response semantics, nonce claim, and certificate/package claim names for your SDK version.
- Do not treat decoded JWT payloads as proof of authenticity. Only the provider verification result establishes signature/provider validity.
- Add automated tests and review failure/timeout behavior before production deployment.

## Environment variables
- `META_APP_ACCESS_TOKEN`: server-side Meta app access token.
- `META_PACKAGE_ID`: expected package/application identifier for your app.
- `META_ALLOWED_CERT_SHA256`: expected signing certificate SHA-256 fingerprint (hex, with or without colons).
- `META_VERIFY_URL`: override only if Meta's current docs specify a different endpoint.
