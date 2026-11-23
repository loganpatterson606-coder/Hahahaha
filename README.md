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
## Configure registered studios (required)

In Render → your service → Environment, add one variable named `STUDIO_PROFILES_JSON`. Its value is a JSON array. Each studio has its own Meta App Access Token, package ID, signing-certificate SHA-256 allow-list, and authorised Quest serial-number allow-list. Example (replace every placeholder with your real values):

```json
[
  {
    "id": "studio-one",
    "name": "Studio One",
    "package_id": "com.example.questapp",
    "access_token": "OC|YOUR_APP_ID|YOUR_APP_SECRET",
    "allowed_cert_sha256": [
      "REPLACE_WITH_64_HEX_CHARACTER_SHA256_DIGEST"
    ],
    "allowed_device_serials": [
      "REPLACE_WITH_REGISTERED_QUEST_SERIAL"
    ]
  }
]
```

Add one object per studio. The `id` must be unique and contain only letters, numbers, underscores or hyphens. The package ID must be the exact Android package ID for that studio's own app. Add each authorised device serial exactly as provided by your device inventory. Keep this variable private in Render; never put App Access Tokens, App Secrets, certificate digests or serial allow-lists in frontend files or GitHub.

The browser receives only studio IDs and display names. When a user selects a studio and enters a serial, the backend checks the serial against that studio's server-side allow-list before issuing a challenge. The challenge permanently records the studio, registered serial, package ID and nonce. During verification, the backend selects that studio's private Meta credential and rechecks that the device remains registered. A successful serial lookup is only an association check; only a genuine Meta-issued token passing provider verification and the configured claim policy can produce a Verified result.

The older single-studio environment variables are supported only if `META_ALLOWED_DEVICE_SERIALS` is also configured. For new deployments, use `STUDIO_PROFILES_JSON`.

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
