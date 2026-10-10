#!/usr/bin/env bash
# One-time Raspberry Pi 4 setup (Tanmay). Run from the project root:  bash hardware/setup_pi.sh
set -euo pipefail

echo "== system packages =="
sudo apt update
sudo apt install -y python3-venv python3-picamera2 python3-gpiozero python3-lgpio i2c-tools libgpiod2 git

echo "== enable I2C (ADS1115) =="
sudo raspi-config nonint do_i2c 0
# Bookworm detects the camera module automatically (camera_auto_detect=1 in /boot/firmware/config.txt).

echo "== python environment =="
# --system-site-packages so the venv can see picamera2 / gpiozero installed by apt
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r hardware/requirements-pi.txt

echo "== check =="
rpicam-hello --list-cameras || libcamera-hello --list-cameras || true
i2cdetect -y 1 || true

cat <<'MSG'

Done. Next steps:
  1. source .venv/bin/activate
  2. python -m hardware.check_components all
  3. leave the MQ-2 powered for 24 h, then: python -m hardware.calibrate_mq2
  4. copy model/weights/best_ncnn_model (from model/export.py) to this Pi
  5. set dashboard.url in config.yaml to the laptop's IP, e.g. http://192.168.1.20:5000
  6. python -m hardware.pi_fire_monitor
MSG
