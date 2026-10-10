import base64

import cv2
import numpy as np
import pytest

from common.config import load_config
from dashboard.app import create_app

KEY = {"X-API-Key": "test-key"}


@pytest.fixture()
def client(tmp_path):
    cfg = load_config(overrides={"dashboard": {"api_key": "test-key"}})
    app = create_app(cfg, db_path=str(tmp_path / "t.db"))
    app.static_folder = str(tmp_path)  # keep snapshots out of the repo
    return app.test_client()


def jpeg_b64():
    ok, buf = cv2.imencode(".jpg", np.zeros((10, 10, 3), np.uint8))
    return base64.b64encode(buf.tobytes()).decode()


def test_page_and_empty_status(client):
    assert client.get("/").status_code == 200
    s = client.get("/api/status").get_json()
    assert s["level"] == "SAFE" and s["devices"] == []


def test_requires_api_key(client):
    assert client.post("/api/events", json={"device": "x", "level": "FIRE"}).status_code == 401


def test_event_flow_and_ack(client):
    r = client.post("/api/events", headers=KEY, json={
        "device": "pi-1", "kind": "raspberry-pi", "level": "FIRE", "label": "fire", "confidence": 0.82,
        "reasons": ["camera sees fire (82%)"], "snapshot_jpeg_b64": jpeg_b64()})
    assert r.status_code == 201
    s = client.get("/api/status").get_json()
    assert s["level"] == "FIRE" and s["active_alerts"] == 1 and s["today"]["fire"] == 1
    events = client.get("/api/events").get_json()
    assert events[0]["snapshot"].endswith(".jpg")
    client.post(f"/api/events/{events[0]['id']}/ack")
    assert client.get("/api/status").get_json()["level"] == "SAFE"
    assert "pi-1" in client.get("/api/events.csv").get_data(as_text=True)


def test_reading_is_fused(client):
    r = client.post("/api/readings", headers=KEY, json={"device": "pi-1", "temperature": 62, "smoke": 70})
    assert r.get_json()["level"] == "FIRE"
    s = client.get("/api/status").get_json()
    assert s["level"] == "FIRE" and s["readings"][0]["temperature"] == 62
    assert len(client.get("/api/readings?minutes=5").get_json()) == 1


def test_frame_upload_and_bad_input(client):
    assert client.post("/api/devices/pi-1/frame", headers=KEY, json={"jpeg_b64": jpeg_b64()}).status_code == 200
    assert client.get("/api/devices/pi-1/frame.jpg").mimetype == "image/jpeg"
    assert client.post("/api/devices/pi-1/frame", headers=KEY, json={"jpeg_b64": "nope!"}).status_code == 400
    assert client.post("/api/events", headers=KEY, json={"device": "x", "level": "BOOM"}).status_code == 400
