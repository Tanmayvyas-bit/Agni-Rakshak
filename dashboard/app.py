"""Web dashboard (Tanishk) - one place to watch every camera and sensor.

    python -m dashboard.app            # then open http://localhost:5000

Devices (laptop detector, desktop GUI, Raspberry Pi) send JSON to the /api/* endpoints with the
X-API-Key header from config.yaml. The browser page polls /api/status every 2 seconds.
"""
from __future__ import annotations

import base64
import binascii
import csv
import io
import logging
import threading
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

import cv2
from flask import Flask, Response, abort, jsonify, render_template, request

from common.config import load_config, resolve
from common.detector import FireDetector
from common.fusion import FIRE, SAFE, WARNING, Reading, assess

from .camera import CameraWorker
from .db import Database

LEVEL_RANK = {SAFE: 0, WARNING: 1, FIRE: 2}
ONLINE_SECONDS = 30          # a device is "online" if it reported in the last 30 s
ACTIVE_ALERT_SECONDS = 300   # unacknowledged alerts keep the banner red for 5 min

log = logging.getLogger("dashboard")


def create_app(cfg: dict | None = None, db_path: str | None = None) -> Flask:
    cfg = cfg or load_config()
    app = Flask(__name__)
    app.config["FIRE_CFG"] = cfg
    db = Database(db_path or str(resolve(cfg["dashboard"]["database"])))
    snapshot_dir = Path(app.static_folder) / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    frames: dict[str, tuple[float, bytes]] = {}   # latest preview JPEG per device (memory only)
    frames_lock = threading.Lock()

    def save_snapshot(device: str, jpeg: bytes) -> str:
        name = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{''.join(ch for ch in device if ch.isalnum() or ch in '-_')}.jpg"
        (snapshot_dir / name).write_bytes(jpeg)
        return name

    def on_local_alert(level, label, confidence, frame, assessment, mode):
        ok, buf = cv2.imencode(".jpg", frame)
        db.touch_device("dashboard-camera", "laptop", "127.0.0.1")
        db.add_event(device="dashboard-camera", level=level, label=label, confidence=confidence,
                     score=assessment.score, reasons="; ".join(assessment.reasons), detector_mode=mode,
                     snapshot=save_snapshot("dashboard-camera", buf.tobytes()) if ok else None)

    def make_detector():
        m = cfg["model"]
        return FireDetector(resolve(m["weights"]), conf=m["conf"], iou=m["iou"], imgsz=m["imgsz"],
                            allow_demo=m["allow_demo_detector"])

    camera = CameraWorker(cfg, make_detector, on_local_alert)
    app.extensions["fire_camera"] = camera
    app.extensions["fire_db"] = db

    def require_key(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if request.headers.get("X-API-Key") != cfg["dashboard"]["api_key"]:
                return jsonify(error="invalid or missing X-API-Key"), 401
            return fn(*a, **kw)
        return wrapper

    def body() -> dict:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            abort(400, "expected a JSON object")
        if not str(data.get("device", "")).strip() and request.endpoint != "post_frame":
            abort(400, "'device' is required")
        return data

    def decode_jpeg(b64: str | None) -> bytes | None:
        if not b64:
            return None
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            abort(400, "image is not valid base64")
        if not raw.startswith(b"\xff\xd8"):
            abort(400, "image must be a JPEG")
        return raw

    def num(value):
        return None if value is None or value == "" else float(value)

    # ---------------------------------------------------------------- pages
    @app.get("/")
    def index():
        return render_template("index.html")

    # ---------------------------------------------------------------- device -> dashboard
    @app.post("/api/events")
    @require_key
    def post_event():
        d = body()
        level = str(d.get("level", WARNING)).upper()
        if level not in (WARNING, FIRE):
            abort(400, "level must be WARNING or FIRE")
        jpeg = decode_jpeg(d.get("snapshot_jpeg_b64"))
        db.touch_device(d["device"], d.get("kind"), request.remote_addr)
        reasons = d.get("reasons")
        event_id = db.add_event(
            device=d["device"], level=level, label=d.get("label"), confidence=num(d.get("confidence")),
            score=d.get("score"), temperature=num(d.get("temperature")), smoke=num(d.get("smoke")),
            reasons="; ".join(reasons) if isinstance(reasons, list) else reasons,
            detector_mode=d.get("detector_mode"),
            snapshot=save_snapshot(d["device"], jpeg) if jpeg else None)
        return jsonify(id=event_id), 201

    @app.post("/api/readings")
    @require_key
    def post_reading():
        d = body()
        reading = Reading(fire_conf=num(d.get("fire_conf")) or 0.0, smoke_conf=num(d.get("smoke_conf")) or 0.0,
                          temperature_c=num(d.get("temperature")), smoke_pct=num(d.get("smoke")),
                          smoke_digital=bool(d.get("smoke_digital")))
        result = assess(reading, cfg["fusion"])
        db.touch_device(d["device"], d.get("kind"), request.remote_addr)
        db.add_reading(device=d["device"], temperature=reading.temperature_c, humidity=num(d.get("humidity")),
                       smoke=reading.smoke_pct, smoke_digital=int(reading.smoke_digital),
                       fire_conf=reading.fire_conf, score=result.score, level=result.level)
        return jsonify(level=result.level, score=result.score, reasons=result.reasons), 201

    @app.post("/api/devices/<device>/frame")
    @require_key
    def post_frame(device):
        d = body()
        jpeg = decode_jpeg(d.get("jpeg_b64"))
        if not jpeg:
            abort(400, "jpeg_b64 is required")
        with frames_lock:
            frames[device] = (time.time(), jpeg)
        db.touch_device(device, d.get("kind"), request.remote_addr)
        return jsonify(ok=True)

    # ---------------------------------------------------------------- browser <- dashboard
    @app.get("/api/devices/<device>/frame.jpg")
    def get_frame(device):
        with frames_lock:
            item = frames.get(device)
        if not item:
            abort(404)
        return Response(item[1], mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/status")
    def status():
        now = time.time()
        level, score, reasons = SAFE, 0, []

        latest = {r["device"]: r for r in db.latest_readings() if now - r["ts"] <= ONLINE_SECONDS}
        for r in latest.values():
            if LEVEL_RANK[r["level"]] > LEVEL_RANK[level]:
                level = r["level"]
            score = max(score, r["score"] or 0)
        active = db.unacknowledged_since(now - ACTIVE_ALERT_SECONDS)
        for e in active:
            if LEVEL_RANK[e["level"]] > LEVEL_RANK[level]:
                level = e["level"]
            score = max(score, e["score"] or (80 if e["level"] == FIRE else 40))
            reasons.append(f"{e['device']}: {e['label'] or e['level']} at {datetime.fromtimestamp(e['ts']):%H:%M:%S}")
        if camera.running and LEVEL_RANK[camera.last_level] > LEVEL_RANK[level]:
            level = camera.last_level

        with frames_lock:
            frame_devices = {k for k, (ts, _) in frames.items() if now - ts <= ONLINE_SECONDS}
        devices = [{**dv, "online": now - (dv["last_seen"] or 0) <= ONLINE_SECONDS,
                    "has_frame": dv["id"] in frame_devices} for dv in db.devices()]
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return jsonify(
            level=level, score=min(score, 100), reasons=reasons[:5], active_alerts=len(active),
            readings=list(latest.values()), devices=devices, today=db.counts_since(midnight),
            camera={"running": camera.running, "fps": round(camera.fps, 1), "mode": camera.mode,
                    "error": camera.error, "level": camera.last_level},
            server_time=now)

    @app.get("/api/events")
    def list_events():
        limit = min(int(request.args.get("limit", 50)), 500)
        return jsonify(db.events(limit))

    @app.get("/api/events.csv")
    def export_events():
        buf = io.StringIO()
        rows = db.events(5000)
        cols = ["id", "time", "device", "level", "label", "confidence", "score", "temperature", "smoke",
                "reasons", "detector_mode", "acknowledged"]
        w = csv.writer(buf)
        w.writerow(cols)
        for r in rows:
            r["time"] = datetime.fromtimestamp(r["ts"]).isoformat(sep=" ", timespec="seconds")
            w.writerow([r.get(c) for c in cols])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=fire_events.csv"})

    @app.post("/api/events/<int:event_id>/ack")
    def ack_event(event_id):
        return jsonify(updated=db.acknowledge(event_id))

    @app.post("/api/events/ack_all")
    def ack_all():
        return jsonify(updated=db.acknowledge())

    @app.get("/api/readings")
    def list_readings():
        minutes = min(float(request.args.get("minutes", 30)), 24 * 60)
        return jsonify(db.readings(time.time() - minutes * 60, request.args.get("device")))

    # ---------------------------------------------------------------- local laptop camera
    @app.post("/api/camera/start")
    def camera_start():
        source = (request.get_json(silent=True) or {}).get("source")
        camera.start(source)
        return jsonify(running=True)

    @app.post("/api/camera/stop")
    def camera_stop():
        camera.stop()
        return jsonify(running=False)

    @app.get("/video_feed")
    def video_feed():
        def stream():
            while camera.running:
                jpeg = camera.latest_jpeg()
                if jpeg:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                time.sleep(0.05)
        return Response(stream(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.errorhandler(400)
    def bad_request(err):
        return jsonify(error=getattr(err, "description", str(err))), 400

    return app


def main():
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    app = create_app(cfg)
    print(f"Dashboard on http://localhost:{cfg['dashboard']['port']}")
    app.run(host=cfg["dashboard"]["host"], port=cfg["dashboard"]["port"], threaded=True, debug=False)


if __name__ == "__main__":
    main()
