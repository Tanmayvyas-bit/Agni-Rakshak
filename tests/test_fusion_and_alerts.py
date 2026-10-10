from common.alerts import AlertTracker
from common.fusion import FIRE, SAFE, WARNING, Reading, assess


def test_nothing_is_safe():
    a = assess(Reading(temperature_c=28, smoke_pct=2))
    assert a.level == SAFE and a.score < 30


def test_camera_only_low_confidence_is_warning():
    assert assess(Reading(fire_conf=0.4)).level == WARNING


def test_camera_high_confidence_is_fire():
    assert assess(Reading(fire_conf=0.8)).level == FIRE


def test_camera_plus_sensor_is_fire():
    a = assess(Reading(fire_conf=0.4, temperature_c=50))
    assert a.level == FIRE and a.score >= 70
    assert any("temperature" in r for r in a.reasons)


def test_one_sensor_alone_is_only_warning():
    assert assess(Reading(temperature_c=60, smoke_pct=5)).level == WARNING
    assert assess(Reading(temperature_c=25, smoke_pct=60)).level == WARNING
    assert assess(Reading(smoke_digital=True)).level == WARNING


def test_both_sensors_high_is_fire_without_camera():
    assert assess(Reading(temperature_c=60, smoke_pct=60)).level == FIRE


def test_alert_tracker_needs_consecutive_frames_and_cooldown():
    now = [0.0]
    t = AlertTracker(min_consecutive_frames=3, cooldown_seconds=10, clock=lambda: now[0])
    assert [t.update(True) for _ in range(3)] == [False, False, True]
    assert t.update(True) is False            # still in cooldown
    t.update(False)                            # streak broken
    now[0] = 11
    assert [t.update(True) for _ in range(3)] == [False, False, True]
