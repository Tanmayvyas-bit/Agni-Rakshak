"""Raspberry Pi 4 sensor and output drivers (Tanmay).

Hardware (see docs/images/circuit_diagram.svg):
  DHT22  temperature/humidity  DATA -> GPIO4 (pin 7), 10 kΩ pull-up to 3.3 V
  MQ-2   smoke/gas             AO -> 10k/20k divider -> ADS1115 A0 (I2C 0x48 on GPIO2/3)
                               DO -> 10k/20k divider -> GPIO17 (pin 11)
  Buzzer (active, 5 V)         driven by 2N2222 transistor from GPIO27 (pin 13)
  Red LED  GPIO22 (pin 15),  Green LED  GPIO23 (pin 16), each through 330 Ω

Every class has a simulated twin so the whole pipeline (and the dashboard) can be demonstrated
on a laptop with `--simulate` before the hardware arrives.
"""
from __future__ import annotations

import json
import logging
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)
CALIBRATION_FILE = Path(__file__).resolve().parent / "mq2_calibration.json"
ADS_VREF = 4.096   # ADS1115 at gain 1 measures 0 - 4.096 V (we never exceed 3.3 V)


@dataclass
class SensorSnapshot:
    temperature: float | None
    humidity: float | None
    smoke_pct: float | None
    smoke_voltage: float | None
    smoke_digital: bool


# --------------------------------------------------------------------- temperature
class DHT22Sensor:
    def __init__(self, gpio: int = 4):
        import adafruit_dht
        import board

        self._dev = adafruit_dht.DHT22(getattr(board, f"D{gpio}"), use_pulseio=False)
        self._last = (None, None)

    def read(self) -> tuple[float | None, float | None]:
        # The DHT22 often fails a single read (timing-sensitive protocol); retry and keep the last good value.
        for _ in range(3):
            try:
                t, h = self._dev.temperature, self._dev.humidity
                if t is not None:
                    self._last = (float(t), float(h) if h is not None else None)
                    return self._last
            except RuntimeError:
                time.sleep(0.5)
        return self._last


# --------------------------------------------------------------------- smoke
class MQ2Sensor:
    """MQ-2 analog voltage via ADS1115, converted to "% above clean-air baseline".

    The MQ-2 cannot give a calibrated smoke ppm without lab gas, so we report how far the
    reading has risen above the clean-air baseline measured by calibrate_mq2.py:
        smoke_pct = (V - V_clean) / (V_max - V_clean) * 100
    """

    def __init__(self, channel: int = 0, address: int = 0x48, divider_ratio: float = 1.5, digital_gpio: int = 17):
        import adafruit_ads1x15.ads1115 as ADS
        import board
        import busio
        from adafruit_ads1x15.analog_in import AnalogIn
        from gpiozero import DigitalInputDevice

        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=address)
        ads.gain = 1
        try:   # adafruit-circuitpython-ads1x15 >= 3.0
            from adafruit_ads1x15.ads1x15 import Pin
            ain = getattr(Pin, f"A{channel}")
        except ImportError:   # 2.x
            ain = getattr(ADS, f"P{channel}")
        self._chan = AnalogIn(ads, ain)
        self._ratio = divider_ratio
        # DO is active-LOW on most MQ-2 modules: LOW = gas above the potentiometer threshold
        self._do = DigitalInputDevice(digital_gpio, pull_up=None, active_state=False)
        cal = load_calibration()
        self.v_clean = cal["v_clean"]
        self.v_max = cal["v_max"]

    def voltage(self) -> float:
        """Real MQ-2 AO voltage (0 - 5 V), undoing the resistor divider."""
        return self._chan.voltage * self._ratio

    def read(self) -> tuple[float, float, bool]:
        v = self.voltage()
        return smoke_percent(v, self.v_clean, self.v_max), v, bool(self._do.value)


def smoke_percent(v: float, v_clean: float, v_max: float) -> float:
    if v_max <= v_clean:
        return 0.0
    return round(max(0.0, min(100.0, (v - v_clean) / (v_max - v_clean) * 100)), 1)


def load_calibration() -> dict:
    if CALIBRATION_FILE.exists():
        return json.loads(CALIBRATION_FILE.read_text())
    log.warning("MQ-2 not calibrated yet - run `python -m hardware.calibrate_mq2` in clean air. Using defaults.")
    return {"v_clean": 0.6, "v_max": 4.0}


# --------------------------------------------------------------------- outputs
class Indicators:
    """Green LED = safe, red LED blinking = warning, red LED + buzzer = fire."""

    def __init__(self, buzzer_gpio=27, red_gpio=22, green_gpio=23):
        from gpiozero import LED, Buzzer

        self.buzzer, self.red, self.green = Buzzer(buzzer_gpio), LED(red_gpio), LED(green_gpio)
        self._level = None

    def show(self, level: str) -> None:
        if level == self._level:
            return
        self._level = level
        self.buzzer.off(); self.red.off(); self.green.off()
        if level == "SAFE":
            self.green.on()
        elif level == "WARNING":
            self.red.blink(on_time=0.5, off_time=0.5)
        else:
            self.red.on()
            self.buzzer.beep(on_time=0.3, off_time=0.2)

    def off(self) -> None:
        self.buzzer.off(); self.red.off(); self.green.off()


# --------------------------------------------------------------------- simulation
class SimulatedSensors:
    """Fake but realistic values. Every ~2 minutes a 'fire' ramps temperature and smoke up."""

    def __init__(self, fire_every: float = 120.0):
        self.t0 = time.time()
        self.fire_every = fire_every

    def read(self) -> SensorSnapshot:
        t = (time.time() - self.t0) % self.fire_every
        fire = max(0.0, math.sin(math.pi * (t - self.fire_every * 0.7) / (self.fire_every * 0.3))) if t > self.fire_every * 0.7 else 0.0
        temp = 28 + 2 * math.sin(time.time() / 60) + 35 * fire + random.uniform(-0.3, 0.3)
        smoke = max(0.0, 3 + 70 * fire + random.uniform(-1.5, 1.5))
        return SensorSnapshot(round(temp, 1), round(55 - 20 * fire + random.uniform(-1, 1), 1),
                              round(smoke, 1), round(0.6 + smoke / 100 * 3.4, 2), smoke > 45)


class SimulatedIndicators:
    def __init__(self, *_, **__):
        self._level = None

    def show(self, level: str) -> None:
        if level != self._level:
            log.info("[indicators] %s", {"SAFE": "green LED on", "WARNING": "red LED blinking",
                                         "FIRE": "red LED + BUZZER"}[level])
            self._level = level

    def off(self) -> None:
        pass


class SensorHub:
    """One object that reads everything, real or simulated."""

    def __init__(self, cfg: dict, simulate: bool = False):
        s = cfg["sensors"]
        self.simulate = simulate
        if simulate:
            self._sim = SimulatedSensors()
            self.indicators = SimulatedIndicators()
            return
        self._dht = DHT22Sensor(s["dht_pin"])
        self._mq2 = MQ2Sensor(s["mq2_channel"], int(s["ads1115_address"]), s["mq2_divider_ratio"], s["mq2_digital_pin"])
        self.indicators = Indicators(s["buzzer_pin"], s["red_led_pin"], s["green_led_pin"])

    def read(self) -> SensorSnapshot:
        if self.simulate:
            return self._sim.read()
        temp, hum = self._dht.read()
        pct, volts, digital = self._mq2.read()
        return SensorSnapshot(temp, hum, pct, round(volts, 3), digital)
