# ATTEST // STUDIO

A Flask demo app for generating and verifying locally signed test JWTs with standard and Meta-shaped simulation profiles.

## Files
- `app.py` — Flask backend and API routes
- `templates/index.html` — animated frontend
- `requirements.txt` — Python dependencies
- `Procfile` — Render start command

## Run locally
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Deploy to Render
Create a Web Service from this repository:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Add environment variable `ATTESTATION_SECRET` with a long random secret.

The app's Meta-shaped profiles are local simulations. They are not issued by Meta and cannot provide genuine Quest device/app attestation. Standard challenges are stored in process memory for this demo; use Redis or a database if deploying multiple workers or instances.
