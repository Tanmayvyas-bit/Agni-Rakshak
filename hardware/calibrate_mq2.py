"""Measure the MQ-2 clean-air baseline (Tanmay). Run once after a 24 h burn-in, in fresh air.

    python -m hardware.calibrate_mq2 --seconds 60

The MQ-2 heater needs ~24-48 h the first time and ~2-3 minutes after every power-up before its
readings are stable. Readings drift with temperature/humidity, so recalibrate on demo day.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time

from common.config import load_config

from .sensors import CALIBRATION_FILE, MQ2Sensor


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=int, default=60)
    p.add_argument("--v-max", type=float, default=4.0, help="AO voltage treated as 100 %% smoke")
    args = p.parse_args(argv)
    s = load_config()["sensors"]
    mq2 = MQ2Sensor(s["mq2_channel"], int(s["ads1115_address"]), s["mq2_divider_ratio"], s["mq2_digital_pin"])

    print(f"Sampling clean air for {args.seconds} s - keep the sensor away from smoke, gas and breath...")
    samples = []
    end = time.time() + args.seconds
    while time.time() < end:
        samples.append(mq2.voltage())
        time.sleep(0.5)
    v_clean = statistics.median(samples)
    data = {"v_clean": round(v_clean, 3), "v_max": args.v_max, "samples": len(samples),
            "stdev": round(statistics.pstdev(samples), 4), "calibrated_at": time.strftime("%Y-%m-%d %H:%M")}
    CALIBRATION_FILE.write_text(json.dumps(data, indent=2))
    print(json.dumps(data, indent=2))
    print(f"saved to {CALIBRATION_FILE}")


if __name__ == "__main__":
    main()
