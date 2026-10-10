"""SQLite storage for the dashboard: alert events, sensor readings and known devices."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    device TEXT NOT NULL,
    level TEXT NOT NULL,             -- WARNING / FIRE
    label TEXT,                      -- fire / smoke / sensor
    confidence REAL,
    score INTEGER,
    temperature REAL,
    smoke REAL,
    reasons TEXT,
    detector_mode TEXT,
    snapshot TEXT,                   -- file name under static/snapshots
    acknowledged INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    device TEXT NOT NULL,
    temperature REAL,
    humidity REAL,
    smoke REAL,
    smoke_digital INTEGER,
    fire_conf REAL,
    score INTEGER,
    level TEXT
);
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    kind TEXT,
    ip TEXT,
    last_seen REAL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def touch_device(self, device: str, kind: str | None, ip: str | None) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT INTO devices(id, kind, ip, last_seen) VALUES(?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET kind=COALESCE(excluded.kind, kind), ip=excluded.ip, last_seen=excluded.last_seen",
                (device, kind, ip, time.time()),
            )

    def add_event(self, **e) -> int:
        cols = ["ts", "device", "level", "label", "confidence", "score", "temperature", "smoke",
                "reasons", "detector_mode", "snapshot"]
        e.setdefault("ts", time.time())
        with self.conn() as c:
            cur = c.execute(f"INSERT INTO events({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                            [e.get(k) for k in cols])
            return cur.lastrowid

    def add_reading(self, **r) -> int:
        cols = ["ts", "device", "temperature", "humidity", "smoke", "smoke_digital", "fire_conf", "score", "level"]
        r.setdefault("ts", time.time())
        with self.conn() as c:
            cur = c.execute(f"INSERT INTO readings({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                            [r.get(k) for k in cols])
            return cur.lastrowid

    def events(self, limit: int = 50) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))]

    def acknowledge(self, event_id: int | None = None) -> int:
        with self.conn() as c:
            if event_id is None:
                return c.execute("UPDATE events SET acknowledged=1 WHERE acknowledged=0").rowcount
            return c.execute("UPDATE events SET acknowledged=1 WHERE id=?", (event_id,)).rowcount

    def unacknowledged_since(self, since: float) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM events WHERE acknowledged=0 AND ts>=? ORDER BY ts DESC", (since,))]

    def readings(self, since: float, device: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM readings WHERE ts>=?", [since]
        if device:
            q += " AND device=?"
            args.append(device)
        with self.conn() as c:
            return [dict(r) for r in c.execute(q + " ORDER BY ts", args)]

    def latest_readings(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT r.* FROM readings r JOIN (SELECT device, MAX(ts) ts FROM readings GROUP BY device) m "
                "ON r.device=m.device AND r.ts=m.ts")]

    def devices(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM devices ORDER BY last_seen DESC")]

    def counts_since(self, since: float) -> dict:
        with self.conn() as c:
            row = c.execute(
                "SELECT COUNT(*) total, SUM(level='FIRE') fire, SUM(level='WARNING') warning "
                "FROM events WHERE ts>=?", (since,)).fetchone()
            return {k: int(row[k] or 0) for k in ("total", "fire", "warning")}
