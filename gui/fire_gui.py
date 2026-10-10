"""Desktop GUI for the fire detector (Shubham).

    python -m gui.fire_gui

Tkinter ships with Python, so the GUI runs on Windows, macOS, Linux and the Raspberry Pi
desktop with no extra install apart from Pillow. Video capture + YOLOv8 run in a background
thread; the Tk main loop only draws, so the window never freezes.
"""
from __future__ import annotations

import queue
import socket
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

from common.alerts import AlertTracker, beep
from common.config import PROJECT_ROOT, load_config, resolve
from common.dashboard_client import DashboardClient
from common.detector import FireDetector, annotate, best_confidence
from common.fusion import Reading, assess

LEVEL_COLORS = {"SAFE": "#1f9d55", "WARNING": "#e08a00", "FIRE": "#d62828", "OFF": "#555555"}


class DetectionWorker(threading.Thread):
    """Reads the camera, runs the detector and pushes results into a queue for the GUI."""

    def __init__(self, source, detector: FireDetector, cfg: dict, out: queue.Queue, client: DashboardClient | None):
        super().__init__(daemon=True)
        self.source, self.detector, self.cfg, self.out, self.client = source, detector, cfg, out, client
        self.stop_event = threading.Event()
        self.tracker = AlertTracker(cfg["alerts"]["min_consecutive_frames"], cfg["alerts"]["cooldown_seconds"])

    def run(self):
        cap = cv2.VideoCapture(int(self.source) if str(self.source).isdigit() else self.source)
        if not cap.isOpened():
            self.out.put(("error", f"Cannot open camera / video: {self.source}"))
            return
        is_file = not str(self.source).isdigit()
        frame_gap = 1.0 / (cap.get(cv2.CAP_PROP_FPS) or 25) if is_file else 0.0   # play files at real speed
        fps, last, n = 0.0, time.time(), 0
        while not self.stop_event.is_set():
            if frame_gap:
                time.sleep(max(0.0, frame_gap - (time.time() - last)))
            ok, frame = cap.read()
            if not ok:
                self.out.put(("error", "Video ended or camera disconnected."))
                break
            n += 1
            dets = self.detector.detect(frame)
            fire, smoke = best_confidence(dets, "fire"), best_confidence(dets, "smoke")
            result = assess(Reading(fire_conf=fire, smoke_conf=smoke), self.cfg["fusion"])
            now = time.time()
            fps = 0.9 * fps + 0.1 / max(now - last, 1e-6)
            last = now
            shown = annotate(frame, dets, self.detector.mode, result.level, fps)
            alert = self.tracker.update(fire > 0 or smoke > 0)
            if alert and self.client:
                self.client.send_event(result.level, "fire" if fire >= smoke else "smoke", max(fire, smoke), shown,
                                       score=result.score, reasons=result.reasons, detector_mode=self.detector.mode)
            if self.client and n % 15 == 0:
                self.client.send_frame(shown)
            # drop old frames if the GUI is slower than the camera
            if self.out.qsize() > 2:
                try:
                    self.out.get_nowait()
                except queue.Empty:
                    pass
            self.out.put(("frame", shown, dets, result, fps, alert))
        cap.release()


class FireApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.title("Smart Fire Detection - Control Panel")
        self.geometry("1200x720")
        self.minsize(960, 600)
        self.queue: queue.Queue = queue.Queue()
        self.worker: DetectionWorker | None = None
        self.detector: FireDetector | None = None
        self.last_frame = None
        self.total_alerts = 0
        self._photo = None

        self.source_var = tk.StringVar(value=str(self.cfg["camera"]["source"]))
        self.weights_var = tk.StringVar(value=str(resolve(self.cfg["model"]["weights"])))
        self.conf_var = tk.DoubleVar(value=self.cfg["model"]["conf"])
        self.sound_var = tk.BooleanVar(value=self.cfg["alerts"]["sound"])
        self.dashboard_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Camera off")

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(30, self._poll_queue)
        self.after(3000, self._poll_sensors)

    # ------------------------------------------------------------------ layout
    def _build(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.banner = tk.Label(self, text="CAMERA OFF", font=("Segoe UI", 18, "bold"), fg="white",
                               bg=LEVEL_COLORS["OFF"], pady=8)
        self.banner.pack(fill="x")

        body = ttk.Frame(self, padding=8)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # video
        video_box = ttk.LabelFrame(body, text="Live view", padding=4)
        video_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.video = tk.Label(video_box, bg="black", fg="#aaa", text="Press  ▶ Start  to begin detection")
        self.video.pack(fill="both", expand=True)

        # controls
        side = ttk.Frame(body)
        side.grid(row=0, column=1, sticky="nsew")

        ctl = ttk.LabelFrame(side, text="Controls", padding=8)
        ctl.pack(fill="x")
        ttk.Label(ctl, text="Camera / video source").grid(row=0, column=0, sticky="w")
        src_row = ttk.Frame(ctl)
        src_row.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Combobox(src_row, textvariable=self.source_var, values=["0", "1", "2"], width=18).pack(side="left", fill="x", expand=True)
        ttk.Button(src_row, text="Video…", command=self.pick_video).pack(side="left", padx=4)

        ttk.Label(ctl, text="Model weights (.pt)").grid(row=2, column=0, sticky="w")
        w_row = ttk.Frame(ctl)
        w_row.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        ttk.Entry(w_row, textvariable=self.weights_var, width=22).pack(side="left", fill="x", expand=True)
        ttk.Button(w_row, text="Browse…", command=self.pick_weights).pack(side="left", padx=4)

        self.conf_label = ttk.Label(ctl, text=f"Confidence threshold: {self.conf_var.get():.2f}")
        self.conf_label.grid(row=4, column=0, sticky="w")
        ttk.Scale(ctl, from_=0.10, to=0.95, variable=self.conf_var, command=self.on_conf).grid(row=5, column=0, sticky="ew")

        ttk.Checkbutton(ctl, text="Alarm sound", variable=self.sound_var).grid(row=6, column=0, sticky="w", pady=(6, 0))
        ttk.Checkbutton(ctl, text="Send alerts to web dashboard", variable=self.dashboard_var).grid(row=7, column=0, sticky="w")

        btns = ttk.Frame(ctl)
        btns.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        self.start_btn = ttk.Button(btns, text="▶ Start", command=self.start)
        self.start_btn.pack(side="left", expand=True, fill="x")
        self.stop_btn = ttk.Button(btns, text="■ Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(btns, text="📷 Snapshot", command=self.snapshot).pack(side="left", expand=True, fill="x")
        ctl.columnconfigure(0, weight=1)

        stats = ttk.LabelFrame(side, text="Status", padding=8)
        stats.pack(fill="x", pady=8)
        self.stats_labels = {}
        for i, key in enumerate(["Detector", "FPS", "Fire confidence", "Smoke confidence", "Risk score",
                                 "Alerts this session", "Temperature (Pi)", "Smoke sensor (Pi)"]):
            ttk.Label(stats, text=key).grid(row=i, column=0, sticky="w")
            lbl = ttk.Label(stats, text="--", font=("Segoe UI", 10, "bold"))
            lbl.grid(row=i, column=1, sticky="e")
            self.stats_labels[key] = lbl
        stats.columnconfigure(1, weight=1)

        log_box = ttk.LabelFrame(side, text="Alert log", padding=4)
        log_box.pack(fill="both", expand=True)
        self.log = ttk.Treeview(log_box, columns=("time", "level", "what"), show="headings", height=8)
        for col, w in (("time", 70), ("level", 70), ("what", 120)):
            self.log.heading(col, text=col.title())
            self.log.column(col, width=w, anchor="w")
        self.log.tag_configure("FIRE", foreground=LEVEL_COLORS["FIRE"])
        self.log.tag_configure("WARNING", foreground=LEVEL_COLORS["WARNING"])
        self.log.pack(fill="both", expand=True)

        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=(6, 2)).pack(fill="x", side="bottom")

    # ------------------------------------------------------------------ actions
    def pick_video(self):
        path = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv"), ("All", "*.*")])
        if path:
            self.source_var.set(path)

    def pick_weights(self):
        path = filedialog.askopenfilename(initialdir=PROJECT_ROOT / "model" / "weights",
                                          filetypes=[("YOLO weights", "*.pt *.onnx"), ("All", "*.*")])
        if path:
            self.weights_var.set(path)

    def on_conf(self, _=None):
        self.conf_label.config(text=f"Confidence threshold: {self.conf_var.get():.2f}")
        if self.detector:
            self.detector.set_conf(float(self.conf_var.get()))

    def _client(self):
        if not self.dashboard_var.get():
            return None
        d = self.cfg["dashboard"]
        return DashboardClient(d["url"], d["api_key"], device_id=f"gui-{socket.gethostname()}", kind="gui")

    def start(self):
        if self.worker:
            return
        weights = Path(self.weights_var.get())
        try:
            self.status_var.set("Loading model…")
            self.update_idletasks()
            self.detector = FireDetector(weights, conf=float(self.conf_var.get()), iou=self.cfg["model"]["iou"],
                                         imgsz=self.cfg["model"]["imgsz"],
                                         allow_demo=self.cfg["model"]["allow_demo_detector"])
        except Exception as exc:   # noqa: BLE001 - show any loading problem to the user
            messagebox.showerror("Model error", str(exc))
            self.status_var.set("Model failed to load")
            return
        if self.detector.mode == "demo":
            self.status_var.set("No trained weights found - using DEMO colour detector")
        else:
            self.status_var.set(f"Model loaded: {weights.name}")
        self.stats_labels["Detector"].config(text=self.detector.mode.upper())
        self.worker = DetectionWorker(self.source_var.get(), self.detector, self.cfg, self.queue, self._client())
        self.worker.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def stop(self):
        if self.worker:
            self.worker.stop_event.set()
            self.worker = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.banner.config(text="CAMERA OFF", bg=LEVEL_COLORS["OFF"])
        self.status_var.set("Camera off")

    def snapshot(self):
        if self.last_frame is None:
            return
        out = resolve(self.cfg["alerts"]["snapshot_dir"])
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"gui_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        cv2.imwrite(str(path), self.last_frame)
        self.status_var.set(f"Saved {path}")

    # ------------------------------------------------------------------ updates
    def _poll_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                if item[0] == "error":
                    self.stop()
                    messagebox.showwarning("Camera", item[1])
                    break
                _, frame, dets, result, fps, alert = item
                self._show(frame, dets, result, fps, alert)
        except queue.Empty:
            pass
        self.after(30, self._poll_queue)

    def _show(self, frame, dets, result, fps, alert):
        self.last_frame = frame
        w, h = max(self.video.winfo_width(), 320), max(self.video.winfo_height(), 240)
        fh, fw = frame.shape[:2]
        scale = min(w / fw, h / fh)
        rgb = cv2.cvtColor(cv2.resize(frame, (int(fw * scale), int(fh * scale))), cv2.COLOR_BGR2RGB)
        self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.video.config(image=self._photo, text="")

        text = {"SAFE": "✔ SAFE - no fire detected", "WARNING": "⚠ WARNING - possible fire / smoke",
                "FIRE": "🔥 FIRE DETECTED"}[result.level]
        self.banner.config(text=text, bg=LEVEL_COLORS[result.level])
        self.stats_labels["FPS"].config(text=f"{fps:.1f}")
        self.stats_labels["Fire confidence"].config(text=f"{best_confidence(dets, 'fire'):.0%}")
        self.stats_labels["Smoke confidence"].config(text=f"{best_confidence(dets, 'smoke'):.0%}")
        self.stats_labels["Risk score"].config(text=f"{result.score}/100")
        if alert:
            self.total_alerts += 1
            self.stats_labels["Alerts this session"].config(text=str(self.total_alerts))
            what = ", ".join(f"{d.label} {d.confidence:.0%}" for d in dets[:3]) or "-"
            self.log.insert("", 0, values=(datetime.now().strftime("%H:%M:%S"), result.level, what), tags=(result.level,))
            if self.sound_var.get():
                beep()

    def _poll_sensors(self):
        """If the dashboard is reachable, show the Raspberry Pi's latest sensor values in the side panel."""
        if self.dashboard_var.get():
            d = self.cfg["dashboard"]
            client = DashboardClient(d["url"], d["api_key"], device_id="gui", timeout=1.0)

            def fetch():
                s = client.status()
                if s:
                    temps = [r["temperature"] for r in s.get("readings", []) if r.get("temperature") is not None]
                    smokes = [r["smoke"] for r in s.get("readings", []) if r.get("smoke") is not None]
                    self.after(0, lambda: (
                        self.stats_labels["Temperature (Pi)"].config(text=f"{max(temps):.1f} °C" if temps else "--"),
                        self.stats_labels["Smoke sensor (Pi)"].config(text=f"{max(smokes):.0f} %" if smokes else "--")))
            threading.Thread(target=fetch, daemon=True).start()
        self.after(3000, self._poll_sensors)

    def on_close(self):
        self.stop()
        self.destroy()


def main():
    FireApp().mainloop()


if __name__ == "__main__":
    main()
