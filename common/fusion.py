"""Combine the camera (YOLOv8) with the temperature and smoke sensors into one risk level.

The rule set is deliberately simple and explainable so it can be defended in the viva:

* the camera alone can raise a WARNING, and a FIRE alarm only when it is very confident;
* sensors alone can raise a WARNING, and a FIRE alarm when both temperature AND smoke are high;
* camera + any sensor agreeing raises a FIRE alarm (two independent sources = fewer false alarms).
"""
from __future__ import annotations

from dataclasses import dataclass, field

SAFE, WARNING, FIRE = "SAFE", "WARNING", "FIRE"


@dataclass
class Reading:
    fire_conf: float = 0.0          # best "fire" confidence from YOLO in this frame (0-1)
    smoke_conf: float = 0.0         # best "smoke" confidence from YOLO (0-1)
    temperature_c: float | None = None
    smoke_pct: float | None = None  # MQ-2 level above clean-air baseline (0-100)
    smoke_digital: bool = False     # MQ-2 DO pin tripped (threshold set by its potentiometer)


@dataclass
class Assessment:
    level: str
    score: int                      # 0-100, shown on the dashboard gauge
    reasons: list[str] = field(default_factory=list)


DEFAULTS = {
    "temp_warn_c": 45,
    "temp_alarm_c": 57,
    "smoke_warn_pct": 25,
    "smoke_alarm_pct": 50,
    "vision_alarm_conf": 0.60,
}


def _ramp(value: float, low: float, high: float) -> float:
    """0 below `low`, 1 above `high`, linear in between."""
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def assess(reading: Reading, cfg: dict | None = None) -> Assessment:
    c = {**DEFAULTS, **(cfg or {})}
    reasons: list[str] = []

    vision = max(reading.fire_conf, 0.8 * reading.smoke_conf)
    vision_alarm = reading.fire_conf >= c["vision_alarm_conf"]
    vision_seen = vision > 0

    temp = reading.temperature_c
    temp_warn = temp is not None and temp >= c["temp_warn_c"]
    temp_alarm = temp is not None and temp >= c["temp_alarm_c"]
    temp_part = _ramp(temp, c["temp_warn_c"] - 10, c["temp_alarm_c"]) if temp is not None else 0.0

    smoke = reading.smoke_pct
    smoke_warn = reading.smoke_digital or (smoke is not None and smoke >= c["smoke_warn_pct"])
    smoke_alarm = smoke is not None and smoke >= c["smoke_alarm_pct"]
    smoke_part = _ramp(smoke, c["smoke_warn_pct"] / 2, c["smoke_alarm_pct"]) if smoke is not None else 0.0
    if reading.smoke_digital:
        smoke_part = max(smoke_part, 0.6)

    score = round(50 * vision + 25 * temp_part + 25 * smoke_part)

    if reading.fire_conf > 0:
        reasons.append(f"camera sees fire ({reading.fire_conf:.0%})")
    if reading.smoke_conf > 0:
        reasons.append(f"camera sees smoke ({reading.smoke_conf:.0%})")
    if temp_warn:
        reasons.append(f"temperature high ({temp:.1f} °C)")
    if smoke_warn:
        reasons.append(f"smoke sensor high ({smoke or 0:.0f} %)" if smoke is not None else "smoke sensor tripped")

    sensor_warn = temp_warn or smoke_warn
    if (vision_alarm and vision_seen) or (vision_seen and sensor_warn) or (temp_alarm and smoke_alarm):
        level = FIRE
        score = max(score, 70)
    elif vision_seen or sensor_warn or score >= 30:
        level = WARNING
        score = max(score, 30)
    else:
        level = SAFE
    return Assessment(level=level, score=min(score, 100), reasons=reasons)
