from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from flask import Flask, jsonify, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024
TOKEN = os.environ.get("ADB_AGENT_TOKEN", "").strip()
ADB = os.environ.get("ADB_PATH") or shutil.which("adb")
ALLOWED_ORIGIN = os.environ.get("ADB_ALLOWED_ORIGIN", "*")
COMMAND_TIMEOUT = 12


@app.after_request
def cors(response):
    origin = request.headers.get("Origin", "")
    if ALLOWED_ORIGIN == "*" or origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN if ALLOWED_ORIGIN != "*" else origin or "*"
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Agent-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.before_request
def preflight():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.path == "/health":
        return None
    if not TOKEN:
        return jsonify({"ok": False, "error": "ADB_AGENT_TOKEN is not configured"}), 503
    if not secrets_compare(request.headers.get("X-Agent-Token", ""), TOKEN):
        return jsonify({"ok": False, "error": "Unauthorised ADB companion request"}), 401


def secrets_compare(a, b):
    import hmac
    return hmac.compare_digest(str(a), str(b))


def run_adb(args: list[str], timeout: int = COMMAND_TIMEOUT):
    if not ADB:
        return None, "adb executable was not found. Install Android Platform Tools and add adb to PATH."
    try:
        proc = subprocess.run(
            [ADB, *args], capture_output=True, text=True, timeout=timeout,
            check=False, shell=False
        )
        if proc.returncode:
            return None, (proc.stderr.strip() or proc.stdout.strip() or f"adb exited {proc.returncode}")
        return proc.stdout.strip(), None
    except subprocess.TimeoutExpired:
        return None, "ADB command timed out."
    except OSError as exc:
        return None, str(exc)


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Attestation Studio ADB Companion",
        "adb_found": bool(ADB),
        "adb_path": ADB or None,
        "authenticated": bool(TOKEN),
        "timestamp": int(time.time()),
    })


@app.get("/api/devices")
def devices():
    output, err = run_adb(["devices", "-l"])
    if err:
        return jsonify({"ok": False, "error": err, "devices": []}), 503
    items = []
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            items.append({
                "serial": parts[0],
                "state": parts[1],
                "details": " ".join(parts[2:]),
            })
    return jsonify({"ok": True, "devices": items, "count": len(items)})


@app.post("/api/pair")
def pair():
    data = request.get_json(silent=True) or {}
    endpoint = str(data.get("endpoint", "")).strip()
    code = str(data.get("pairing_code", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9.\-_\[\]:]+:\d{1,5}", endpoint):
        return jsonify({"ok": False, "error": "Enter the pairing IP:port shown in Quest Wireless Debugging."}), 400
    if not re.fullmatch(r"\d{6}", code):
        return jsonify({"ok": False, "error": "Pairing code must be six digits."}), 400
    output, err = run_adb(["pair", endpoint, code], timeout=25)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "output": output or "Pairing command completed."})


@app.post("/api/connect")
def connect():
    data = request.get_json(silent=True) or {}
    endpoint = str(data.get("endpoint", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9.\-_\[\]:]+:\d{1,5}", endpoint):
        return jsonify({"ok": False, "error": "Enter the wireless debugging IP:port."}), 400
    output, err = run_adb(["connect", endpoint], timeout=20)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "output": output})


@app.post("/api/disconnect")
def disconnect():
    data = request.get_json(silent=True) or {}
    endpoint = str(data.get("endpoint", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9.\-_\[\]:]+:\d{1,5}", endpoint):
        return jsonify({"ok": False, "error": "Enter the device IP:port."}), 400
    output, err = run_adb(["disconnect", endpoint])
    if err:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "output": output})


@app.post("/api/device-info")
def device_info():
    data = request.get_json(silent=True) or {}
    serial = str(data.get("serial", "")).strip()
    if not serial or len(serial) > 200 or any(ch.isspace() for ch in serial):
        return jsonify({"ok": False, "error": "Select a connected device first."}), 400
    state, err = run_adb(["-s", serial, "get-state"])
    if err or state != "device":
        return jsonify({"ok": False, "error": err or "Device is not in the device state."}), 409

    props = {
        "model": "ro.product.model",
        "manufacturer": "ro.product.manufacturer",
        "android_release": "ro.build.version.release",
        "android_sdk": "ro.build.version.sdk",
        "build_fingerprint": "ro.build.fingerprint",
        "serial": "ro.serialno",
    }
    result = {}
    for label, prop in props.items():
        value, prop_err = run_adb(["-s", serial, "shell", "getprop", prop])
        result[label] = value if not prop_err else None

    battery, battery_err = run_adb(["-s", serial, "shell", "dumpsys", "battery"])
    if not battery_err and battery:
        level = re.search(r"level:\s*(\d+)", battery)
        status = re.search(r"status:\s*(\d+)", battery)
        result["battery_level"] = int(level.group(1)) if level else None
        result["battery_status_code"] = int(status.group(1)) if status else None
    else:
        result["battery_level"] = None
    return jsonify({"ok": True, "device": result})


if __name__ == "__main__":
    # Keep the companion on the private LAN by default. Do not expose it publicly
    # without a secure tunnel, a strong random token, and an explicit origin allowlist.
    app.run(host=os.environ.get("ADB_AGENT_HOST", "0.0.0.0"),
            port=int(os.environ.get("ADB_AGENT_PORT", "8765")),
            debug=False)
