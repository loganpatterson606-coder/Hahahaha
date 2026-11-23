# Attestation Studio — Quest Systems Console

Flat-root project. All files are in the repository root.

## Files
- `app.py` — Render Flask backend, SQLite challenge store, genuine Meta verification, health and optional ADB proxy.
- `index.html`, `style.css`, `app.js` — animated responsive dashboard.
- `adb_agent.py` — optional local PC companion that runs allow-listed ADB operations.
- `requirements.txt`, `Procfile`, `.env.example` — deployment configuration.

## Render deployment
Build command:
```bash
pip install -r requirements.txt
```
Start command:
```bash
gunicorn app:app
```
Set the following Render environment variables:
- `META_APP_ACCESS_TOKEN` — Meta app access token (`OC|APP_ID|APP_SECRET`); keep it server-side.
- `META_PACKAGE_ID` — exact package ID of your own app.
- `META_ALLOWED_CERT_SHA256` — expected signing certificate SHA-256 digest(s), comma-separated.

The app uses SQLite for single-use challenges. For multi-instance/high-availability deployments, move challenge storage to managed PostgreSQL/Redis and configure persistent storage appropriately.

## ADB companion (run on the computer connected to Quest)
Render cannot discover a Quest on your private Wi-Fi. ADB runs on the PC that has Android Platform Tools and network access to the headset.

On that PC:
```bash
pip install -r requirements.txt
```
Set a strong shared secret:
```bash
# macOS/Linux
export ADB_AGENT_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python adb_agent.py
```
Windows PowerShell:
```powershell
$env:ADB_AGENT_TOKEN = "use-a-long-random-secret-here"
python adb_agent.py
```
In the dashboard's ADB Console, enter the PC's reachable address and the same token in the Companion access token field. The browser stores this token in local storage on that device. The agent defaults to port 8765. Install Android SDK Platform Tools and ensure `adb` is on PATH.

On Quest, enable Developer Mode and Wireless Debugging. Use the pairing IP:port and six-digit pairing code shown by Quest's **Pair new device** screen. After pairing, connect using the regular Wireless Debugging IP:port.

Security notes:
- The companion only permits `adb devices -l`, `adb pair`, `adb connect`, `adb disconnect`, `getprop` for a fixed set of system properties, `get-state`, and `dumpsys battery`.
- It does not run arbitrary shell commands, root the device, extract app-private data, or retrieve third-party app tokens.
- Restrict the companion to a trusted LAN. Set `ADB_ALLOWED_ORIGIN` to your dashboard origin when browser access is cross-origin. Do not expose port 8765 directly to the public internet. If remote access is needed, use a private authenticated tunnel.
- The dashboard browser must be able to reach the companion URL. HTTPS pages may block plain-HTTP LAN endpoints depending on browser/platform security policy; use a trusted HTTPS tunnel if needed.

## Genuine Meta attestation flow
The dashboard does not create Meta tokens. The authorised native Quest app must call Meta's Device Application Integrity API with the server-issued nonce. Current Meta documentation describes:
- `DeviceApplicationIntegrity().getIntegrityToken(challengeNonce)` for Kotlin / Android Platform SDK.
- Nonce must be Base64URL, 22–172 characters; this app creates 43-character Base64URL values.
- Verify by calling `https://graph.oculus.com/platform_integrity/verify` with `token` and the server-side App Access Token.
- Successful response contains `data[0].message == "success"` and Base64URL-encoded `data[0].claims`.
- Claims are grouped under `request_details`, `app_state`, and `device_state`.
- This backend checks nonce, expiry, recent timestamp, package ID, `StoreRecognized`, certificate SHA-256 digest, accepted device integrity state, and device ban status.

Meta reference:
https://developers.meta.com/vr/documentation/android-apps/ps-attestation-api/

Supported devices and platform details can change; check the current Meta documentation and SDK version before release. The Attestation API is for Android-platform apps and Meta Quest 2, Quest Pro, Quest 3 and Quest 3S per the current documentation.

## Important limitations
- This is an integration dashboard and backend starter, not a substitute for your native Quest app.
- A browser cannot call the native Quest attestation SDK.
- A valid provider token is app-bound; this service is designed for the package and certificate you configure, not arbitrary third-party games.
- Do not add mock token generation to the Meta path. The only genuine token issuer is Meta's attestation service.
- Before production, add authenticated user sessions, CSRF protection if using cookies, request rate limiting, managed database storage, monitoring, and security review.
