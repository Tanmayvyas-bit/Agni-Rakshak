# 7. Testing and evaluation plan

## 7.1 Automated tests

```bash
pytest            # 16 tests
```
| File | What it checks |
|---|---|
| `tests/test_fusion_and_alerts.py` | Every fusion rule (SAFE/WARNING/FIRE), consecutive-frame debounce, cooldown |
| `tests/test_detector.py` | Demo fallback when weights are missing; detector finds a flame-coloured blob and ignores a dark frame |
| `tests/test_dashboard.py` | API key, event + snapshot storage, acknowledge, server-side fusion, frames, bad input, CSV |
| `tests/test_prepare_dataset.py` | Label validation, class remapping, duplicate removal, split, data.yaml |

## 7.2 Model evaluation (offline)

Run `python -m model.evaluate` on the **test** split and record the results:

| Model | imgsz | Precision | Recall | mAP@50 | mAP@50-95 | ms/img (laptop) | FPS (Pi, NCNN 320) |
|---|---|---|---|---|---|---|---|
| YOLOv8n | 640 | | | | | | |
| YOLOv8s | 640 | | | | | | |
| YOLOv8n | 320 | | | | | | |

## 7.3 Live functional tests (laptop webcam)

Record each test 3 times. "Detected" means an alert within 5 s.

| # | Scenario | Expected | Result | Time to alert |
|---|---|---|---|---|
| F1 | Candle flame at 1 m | FIRE | | |
| F2 | Lighter flame at 2 m | FIRE | | |
| F3 | Burning paper in a steel tray (supervised) | FIRE | | |
| F4 | Incense smoke | smoke WARNING/FIRE | | |
| F5 | Fire video on a phone screen | FIRE | | |
| N1 | Red / orange clothing | no alert | | |
| N2 | Tube light / bulb in frame | no alert | | |
| N3 | Sunset picture / orange wall | no alert | | |
| N4 | Person waving, normal room | no alert | | |
| N5 | Phone torch pointed at the camera | no alert | | |

**False-alarm rate** = false alerts per hour of normal room video. Run 1 hour with no fire and count.

## 7.4 Sensor and fusion tests (Raspberry Pi)

| # | Scenario | Expected level | Result |
|---|---|---|---|
| S1 | Room air | SAFE (green LED) | |
| S2 | Hair dryer on the DHT22 (> 45 °C) | WARNING (red blink) | |
| S3 | Incense smoke on the MQ-2 | WARNING | |
| S4 | Hair dryer + incense together | FIRE (red + buzzer) | |
| S5 | Candle in camera view + warm DHT22 | FIRE | |
| S6 | Dashboard stopped, then restarted | Pi keeps alarming locally; reconnects later | |
| S7 | Wi-Fi off | Local alarm still works | |

## 7.5 System tests

| # | Test | Pass criteria |
|---|---|---|
| T1 | Alert reaches the dashboard | < 2 s after the device alarms |
| T2 | 3 devices at once (laptop, GUI, Pi) | All online, all events listed |
| T3 | 8-hour run | No crash, memory stable |
| T4 | Dashboard on a phone | Readable, no horizontal scroll |
