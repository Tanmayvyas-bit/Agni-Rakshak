# 2. Month-1 plan (weeks 1–4)

**Month-1 goal:** a YOLOv8 model detects fire from the **laptop webcam**. Alerts show up on the **web
dashboard** and the **desktop GUI**. The **Raspberry Pi with camera, temperature and smoke sensors** is wired
and every component is tested individually.

Everyone can start on day 1. Until the real model exists, the code falls back to a demo detector. Tanmay's
sensors can be simulated with `--simulate`.

## Week-by-week tasks

### Week 1: setup and data collection
| Member | Tasks | Done when |
|---|---|---|
| All | Install Python 3.10+, clone the repo, `pip install -r requirements.txt`, run `pytest`, run the dashboard + `webcam_detect` (demo mode) | Everyone has seen the demo running on their own laptop |
| Tanishka | Find 2–3 public fire/smoke datasets (Roboflow Universe, D-Fire, Kaggle). Create a Roboflow workspace. Start collecting own images with `model.collect_frames` (candle, lighter, matchstick, incense smoke, phone videos of bonfires) | ≥ 1,500 public + ≥ 200 own images downloaded |
| Tanishk | Read `dashboard/app.py` and `static/app.js`. Run the dashboard. Sketch improvements (logo, colours, layout) | Dashboard running; written list of UI changes |
| Tanmay | Order parts (see [hardware BOM](05_hardware.md#51-bill-of-materials)). Flash Raspberry Pi OS 64-bit, enable SSH/VNC, run `hardware/setup_pi.sh` | Pi boots, `i2cdetect` and camera test run |
| Shubham | Run `python -m gui.fire_gui`. Study Tkinter `ttk` widgets. Plan the GUI screens on paper | GUI running in demo mode |

### Week 2: labelling and first training
| Member | Tasks | Done when |
|---|---|---|
| Tanishka | Label own images (fire, smoke). Add 15–20 % **negatives** (red clothes, sunsets, bulbs, orange walls). Run `model.prepare_dataset` to merge + split 70/20/10. First training run (YOLOv8n, 50 epochs) on Colab | `best.pt` v0 exists; mAP@50 noted |
| Tanishk | Implement the UI changes. Add device filter and "last updated" text. Test with `pi_fire_monitor --simulate` | Dashboard shows simulated sensor data properly |
| Tanmay | Wire LEDs + buzzer + transistor on a breadboard. Then DHT22. Run `python -m hardware.check_components leds buzzer dht` | LEDs, buzzer and DHT22 pass |
| Shubham | Add a settings dialog (dashboard URL, alert sound, snapshot folder) and an FPS/latency display | GUI v0.5 demo |

### Week 3: full training and integration
| Member | Tasks | Done when |
|---|---|---|
| Tanishka | Train YOLOv8n for 100 epochs and YOLOv8s for comparison. Evaluate on the **test** split with `model.evaluate`. Copy the best to `model/weights/best.pt` and share it on Google Drive | mAP@50 ≥ 0.75 (target 0.80 by month 2) |
| Tanishk | Connect the laptop detector, GUI and simulated Pi at the same time. Check alerts, snapshots, ack and CSV export | All three devices visible on the dashboard |
| Tanmay | Wire MQ-2 + ADS1115 with the voltage dividers. `check_components i2c mq2`. Start the 24 h burn-in, then `calibrate_mq2`. Test the Pi camera | MQ-2 reacts to incense smoke; camera photo OK |
| Shubham | Test the GUI with the trained model. Add a per-alert snapshot preview to the log | GUI works with the real model |

### Week 4: testing, documentation, month-1 demo
| Member | Tasks | Done when |
|---|---|---|
| Tanishka | Test the live webcam against a candle, a lighter, a phone fire video and false-alarm objects. Record results in [07](07_testing_and_evaluation.md) | Test table filled in |
| Tanishk | Take screenshots for the report. Write the API section | Screenshots in `docs/images/` |
| Tanmay | Run `pi_fire_monitor --no-camera` with real sensors, sending to the dashboard on the laptop over Wi-Fi. Take photos of the breadboard | Real temperature/smoke readings on the dashboard |
| Shubham | Fix bugs. Record a 2-minute screen recording of the GUI | Demo video |
| All | Month-1 review with the guide (demo script below). Write a 1-page progress report | Guide sign-off |

## Month-1 demo script (≈10 minutes)

1. Start the dashboard on the laptop (`python -m dashboard.app`) and open it on the projector.
2. **Tanishka:** show the dataset statistics, training curves (`runs/fire/.../results.png`) and metrics table.
   Run `python -m detection.webcam_detect`, light a candle in front of the webcam and show the boxes, the beep and the saved snapshot.
3. **Tanishk:** the alert appears on the dashboard with its snapshot. Show acknowledging it, the sensor chart and CSV export.
4. **Shubham:** start the GUI. Change the threshold live, play a fire video file and show the alert log.
5. **Tanmay:** show the breadboard with the Pi. Breathe or blow incense smoke on the MQ-2 and warm the DHT22 with a hand
   or hair dryer. The values rise on the dashboard and the LEDs/buzzer react.
6. Show the circuit diagram and the 6-month roadmap.

## Month-1 deliverables checklist

- [ ] Dataset v1 (counts per class, train/val/test split) on Google Drive
- [ ] `model/weights/best.pt` + `docs/results/model_metrics.md`
- [ ] Laptop webcam detection working (`detection/webcam_detect.py`)
- [ ] Web dashboard working with ≥ 2 devices
- [ ] Desktop GUI working with the trained model
- [ ] All Pi components tested individually; circuit diagram final
- [ ] Documentation updated; month-1 progress report submitted

## Team working rules

* **Git:** one branch per member (`model/...`, `web/...`, `hw/...`, `gui/...`). Open a pull request into `main`
  and have one teammate review it. Never commit datasets, `runs/` or `.pt` files. Share those via Google Drive.
* **Weekly meeting** (30 min): what I did, what I'll do, what's blocking me. Keep notes in a shared doc.
* **Interfaces are fixed** by `config.yaml` and the API in [04](04_web_dashboard.md#api-reference). Changing a field means telling everyone.
