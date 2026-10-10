"""Check every component one by one before running the full system (Tanmay).

    python -m hardware.check_components all
    python -m hardware.check_components leds | buzzer | dht | mq2 | camera | i2c
"""
from __future__ import annotations

import subprocess
import sys
import time

from common.config import load_config

CFG = load_config()["sensors"]


def check_leds():
    from gpiozero import LED
    for name, pin in (("green", CFG["green_led_pin"]), ("red", CFG["red_led_pin"])):
        led = LED(pin)
        print(f"{name} LED on GPIO{pin} - should blink 3 times")
        for _ in range(3):
            led.on(); time.sleep(0.3); led.off(); time.sleep(0.3)


def check_buzzer():
    from gpiozero import Buzzer
    b = Buzzer(CFG["buzzer_pin"])
    print(f"buzzer on GPIO{CFG['buzzer_pin']} - should beep twice")
    for _ in range(2):
        b.on(); time.sleep(0.3); b.off(); time.sleep(0.3)


def check_i2c():
    print("I2C bus 1 scan - ADS1115 should appear at 48:")
    subprocess.run(["i2cdetect", "-y", "1"], check=False)


def check_dht():
    from .sensors import DHT22Sensor
    s = DHT22Sensor(CFG["dht_pin"])
    for _ in range(5):
        print("temperature %s °C, humidity %s %%" % s.read())
        time.sleep(2)


def check_mq2():
    from .sensors import MQ2Sensor
    s = MQ2Sensor(CFG["mq2_channel"], int(CFG["ads1115_address"]), CFG["mq2_divider_ratio"], CFG["mq2_digital_pin"])
    print("MQ-2: blow out a matchstick / incense near it, the value should rise (Ctrl+C to stop)")
    try:
        while True:
            pct, v, digital = s.read()
            print(f"AO {v:.3f} V  smoke {pct:5.1f} %  DO {'TRIPPED' if digital else 'ok'}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def check_camera():
    from picamera2 import Picamera2
    cam = Picamera2()
    cam.configure(cam.create_still_configuration())
    cam.start(); time.sleep(2)
    cam.capture_file("camera_test.jpg")
    cam.stop()
    print("saved camera_test.jpg - open it to check focus and orientation")


TESTS = {"leds": check_leds, "buzzer": check_buzzer, "i2c": check_i2c, "dht": check_dht, "mq2": check_mq2, "camera": check_camera}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name in (TESTS if which == "all" else [which]):
        print(f"\n=== {name} ===")
        try:
            TESTS[name]()
        except Exception as exc:   # noqa: BLE001 - report and continue with the next part
            print(f"FAILED: {exc}")
