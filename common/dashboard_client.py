"""Small HTTP client that any detector (laptop, GUI, Raspberry Pi) uses to talk to the dashboard.

Uses only the standard library so it also runs on a fresh Raspberry Pi. Network failures are
logged and swallowed: a dashboard that is down must never stop fire detection.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request

import cv2

log = logging.getLogger(__name__)


class DashboardClient:
    def __init__(self, base_url: str, api_key: str, device_id: str, kind: str = "laptop", timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.device_id = device_id
        self.kind = kind
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict | None:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-API-Key", self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode() or "{}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            log.warning("dashboard %s %s failed: %s", method, path, exc)
            return None

    @staticmethod
    def _jpeg_b64(frame, max_width: int = 640, quality: int = 70) -> str:
        h, w = frame.shape[:2]
        if w > max_width:
            frame = cv2.resize(frame, (max_width, int(h * max_width / w)))
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buf.tobytes()).decode() if ok else ""

    def send_event(self, level: str, label: str, confidence: float, frame=None, **extra) -> dict | None:
        payload = {"device": self.device_id, "kind": self.kind, "level": level, "label": label,
                   "confidence": round(float(confidence), 3), **extra}
        if frame is not None:
            payload["snapshot_jpeg_b64"] = self._jpeg_b64(frame)
        return self._request("POST", "/api/events", payload)

    def send_reading(self, **values) -> dict | None:
        return self._request("POST", "/api/readings", {"device": self.device_id, "kind": self.kind, **values})

    def send_frame(self, frame) -> dict | None:
        return self._request("POST", f"/api/devices/{self.device_id}/frame",
                             {"kind": self.kind, "jpeg_b64": self._jpeg_b64(frame, max_width=480, quality=60)})

    def status(self) -> dict | None:
        return self._request("GET", "/api/status")
