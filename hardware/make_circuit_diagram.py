"""Generate docs/images/circuit_diagram.svg (Tanmay can edit pins/labels here and re-run).

    python -m hardware.make_circuit_diagram
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "images" / "circuit_diagram.svg"
W, H = 1460, 1210
parts: list[str] = []

C = {  # wire colours
    "3v3": "#e67e22", "5v": "#d62828", "gnd": "#222222", "dht": "#c9a400", "sda": "#1f6feb", "scl": "#16a085",
    "do": "#8e44ad", "ao": "#b5651d", "buz": "#6d4c41", "red": "#d62828", "green": "#1f9d55",
}


def add(s: str) -> None:
    parts.append(s)


def text(x, y, s, size=13, anchor="start", weight="normal", color="#222", italic=False):
    style = ' font-style="italic"' if italic else ""
    add(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{color}"{style}>{s}</text>')


def wire(points, color, width=2.4):
    pts = " ".join(f"{x},{y}" for x, y in points)
    add(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')


def dot(x, y, color="#222"):
    add(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{color}"/>')


def box(x, y, w, h, title, sub=None, fill="#f7f9fc"):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="#333" stroke-width="2"/>')
    text(x + w / 2, y + 22, title, 15, "middle", "bold")
    if sub:
        text(x + w / 2, y + 40, sub, 11.5, "middle", color="#555")


def pin(x, y, label, side="left"):
    add(f'<circle cx="{x}" cy="{y}" r="4" fill="#fff" stroke="#333" stroke-width="1.6"/>')
    if side == "left":
        text(x + 9, y + 4, label, 12)
    elif side == "right":
        text(x - 9, y + 4, label, 12, "end")
    elif side == "bottom":
        text(x, y - 9, label, 12, "middle")
    elif side == "top":
        text(x, y + 18, label, 12, "middle")


def resistor_h(x1, x2, y, label, color):
    mid = (x1 + x2) / 2
    wire([(x1, y), (mid - 20, y)], color)
    wire([(mid + 20, y), (x2, y)], color)
    add(f'<rect x="{mid - 20}" y="{y - 7}" width="40" height="14" fill="#fff" stroke="#333" stroke-width="1.8"/>')
    text(mid, y - 12, label, 12, "middle", "bold")


def resistor_v(x, y1, y2, label, color, label_side="right"):
    mid = (y1 + y2) / 2
    wire([(x, y1), (x, mid - 20)], color)
    wire([(x, mid + 20), (x, y2)], color)
    add(f'<rect x="{x - 7}" y="{mid - 20}" width="14" height="40" fill="#fff" stroke="#333" stroke-width="1.8"/>')
    if label_side == "right":
        text(x + 12, mid + 4, label, 12, "start", "bold")
    else:
        text(x - 12, mid + 4, label, 12, "end", "bold")


def ground(x, y, lead=14):
    wire([(x, y), (x, y + lead)], C["gnd"])
    y += lead
    for i, half in enumerate((11, 7, 3)):
        add(f'<line x1="{x - half}" y1="{y + i * 4}" x2="{x + half}" y2="{y + i * 4}" stroke="#222" stroke-width="2"/>')


def supply(x, y, label, color, up=True, lead=16):
    """Power flag: every flag with the same label is the same wire (net)."""
    y2 = y - lead if up else y + lead
    wire([(x, y), (x, y2)], color)
    add(f'<line x1="{x - 10}" y1="{y2}" x2="{x + 10}" y2="{y2}" stroke="{color}" stroke-width="3"/>')
    text(x, y2 - 6 if up else y2 + 16, label, 12, "middle", "bold", color)


def led_h(x, y, color, name):
    """Diode pointing right (anode on the left) at x..x+30."""
    add(f'<polygon points="{x},{y - 11} {x},{y + 11} {x + 22},{y}" fill="{color}" stroke="#222" stroke-width="1.5"/>')
    add(f'<line x1="{x + 22}" y1="{y - 11}" x2="{x + 22}" y2="{y + 11}" stroke="#222" stroke-width="2.2"/>')
    for dx in (6, 14):
        add(f'<line x1="{x + dx}" y1="{y - 14}" x2="{x + dx + 8}" y2="{y - 24}" stroke="{color}" stroke-width="1.6" marker-end="url(#arrow)"/>')
    text(x + 11, y + 28, name, 12, "middle", "bold", color)


def npn(cx, cy):
    add(f'<circle cx="{cx}" cy="{cy}" r="26" fill="#fff" stroke="#333" stroke-width="1.8"/>')
    add(f'<line x1="{cx - 10}" y1="{cy - 14}" x2="{cx - 10}" y2="{cy + 14}" stroke="#222" stroke-width="3"/>')
    add(f'<line x1="{cx - 10}" y1="{cy - 6}" x2="{cx + 10}" y2="{cy - 20}" stroke="#222" stroke-width="2"/>')
    add(f'<line x1="{cx - 10}" y1="{cy + 6}" x2="{cx + 10}" y2="{cy + 20}" stroke="#222" stroke-width="2" marker-end="url(#arrow)"/>')
    text(cx + 32, cy + 4, "Q1 2N2222 (NPN)", 12, "start", "bold")
    text(cx + 32, cy + 20, "B=base  C=collector  E=emitter", 11, "start", color="#555")


# ------------------------------------------------------------------ canvas
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI, Roboto, Arial, sans-serif">')
add('<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#222"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(40, 42, "Smart Fire Detection - Raspberry Pi 4 circuit diagram", 24, weight="bold")
text(40, 66, "Pi Camera Module + DHT22 temperature sensor + MQ-2 smoke sensor (via ADS1115 ADC) + buzzer + status LEDs   ·   Hardware owner: Tanmay Vyas", 13.5, color="#555")

# ------------------------------------------------------------------ Raspberry Pi
PI_X, PI_R = 40, 360
add(f'<rect x="{PI_X}" y="90" width="{PI_R - PI_X}" height="910" rx="14" fill="#e8f5e9" stroke="#2e7d32" stroke-width="2.5"/>')
text((PI_X + PI_R) / 2, 120, "Raspberry Pi 4 Model B", 18, "middle", "bold", "#1b5e20")
text((PI_X + PI_R) / 2, 140, "40-pin GPIO header (BCM numbering)", 12, "middle", color="#2e7d32")
TERMS = [  # (y, physical pin, name)
    (190, 1, "3V3 power"), (230, 2, "5V power"), (265, 6, "GND"),
    (320, 7, "GPIO4"), (470, 3, "GPIO2 / SDA"), (510, 5, "GPIO3 / SCL"),
    (640, 11, "GPIO17"), (820, 13, "GPIO27"), (900, 15, "GPIO22"), (960, 16, "GPIO23"),
]
for y, num, name in TERMS:
    text(PI_R - 14, y + 4, f"pin {num:>2} · {name}", 13, "end", "bold" if "GPIO" in name or "SDA" in name else "normal")
    add(f'<rect x="{PI_R - 6}" y="{y - 6}" width="12" height="12" fill="#c9a227" stroke="#333"/>')
text(60, 370, "Any GND pin works:", 12, color="#2e7d32")
text(60, 388, "6, 9, 14, 20, 25, 30, 34, 39", 12, color="#2e7d32")
text(60, 416, "Power: official 5V 3A USB-C", 12, color="#2e7d32")
text(60, 432, "supply (Pi 4 + camera + MQ-2", 12, color="#2e7d32")
text(60, 448, "heater draw ~1.5 A total)", 12, color="#2e7d32")

# power flags at the Pi
wire([(PI_R, 190), (420, 190)], C["3v3"]); supply(420, 190, "3V3", C["3v3"])
wire([(PI_R, 230), (470, 230)], C["5v"]); supply(470, 230, "5V", C["5v"])
wire([(PI_R, 265), (520, 265)], C["gnd"]); ground(520, 265)

# ------------------------------------------------------------------ DHT22
box(760, 170, 170, 220, "DHT22", "temp + humidity")
for y, lab in ((250, "1 VCC"), (320, "2 DATA"), (345, "3 NC"), (370, "4 GND")):
    pin(760, y, lab)
wire([(PI_R, 320), (760, 320)], C["dht"])
text(470, 312, "DATA", 12, color=C["dht"], weight="bold")
wire([(760, 250), (640, 250)], C["3v3"])
supply(640, 250, "3V3", C["3v3"], lead=24)
resistor_v(640, 250, 320, "R1 10 kΩ pull-up", C["3v3"], "left")
dot(640, 250, C["3v3"]); dot(640, 320, C["dht"])
wire([(760, 370), (720, 370)], C["gnd"]); ground(720, 370, lead=10)

# ------------------------------------------------------------------ ADS1115
box(760, 405, 160, 205, "ADS1115", "16-bit ADC, I2C 0x48")
pin(760, 470, "SDA"); pin(760, 510, "SCL"); pin(760, 545, "ADDR"); pin(760, 580, "GND")
pin(920, 520, "A0", "right"); pin(920, 555, "A1-A3 n/c", "right")
pin(920, 470, "VDD", "right")
wire([(920, 470), (970, 470)], C["3v3"]); supply(970, 470, "3V3", C["3v3"], lead=18)
wire([(PI_R, 470), (760, 470)], C["sda"]); text(470, 462, "SDA (I2C data)", 12, color=C["sda"], weight="bold")
wire([(PI_R, 510), (760, 510)], C["scl"]); text(470, 502, "SCL (I2C clock)", 12, color=C["scl"], weight="bold")
wire([(760, 545), (725, 545), (725, 580), (760, 580)], C["gnd"]); dot(725, 580)
ground(725, 580, lead=12)
text(620, 548, "ADDR→GND", 11, color="#555")

# ------------------------------------------------------------------ MQ-2
box(1160, 370, 260, 100, "MQ-2 smoke / gas module", "powered from 5V (heater needs 5V)")
for x, lab in ((1200, "AO"), (1250, "DO"), (1300, "GND"), (1350, "VCC")):
    pin(x, 470, lab, "bottom")
wire([(1350, 470), (1350, 490)], C["5v"]); supply(1350, 490, "5V", C["5v"], up=False, lead=14)
ground(1300, 470, lead=22)
# AO -> 10k/20k divider -> ADS1115 A0  (5V max * 20/30 = 3.33V, safe for the 3.3V ADC)
wire([(1200, 470), (1200, 520)], C["ao"])
resistor_h(1200, 1080, 520, "R2 10 kΩ", C["ao"])
wire([(1080, 520), (920, 520)], C["ao"]); dot(1040, 520, C["ao"])
resistor_v(1040, 520, 600, "R3 20 kΩ", C["ao"], "left")
ground(1040, 600, lead=6)
text(960, 512, "AO ÷1.5", 11, "middle", color=C["ao"], weight="bold")
# DO -> 10k/20k divider -> GPIO17
wire([(1250, 470), (1250, 640)], C["do"])
resistor_h(1250, 1150, 640, "R4 10 kΩ", C["do"])
wire([(1150, 640), (PI_R, 640)], C["do"]); dot(1110, 640, C["do"])
resistor_v(1110, 640, 720, "R5 20 kΩ", C["do"], "right")
ground(1110, 720, lead=6)
text(470, 632, "MQ-2 DO (digital alarm, via divider)", 12, color=C["do"], weight="bold")

# ------------------------------------------------------------------ buzzer driver
wire([(PI_R, 820), (580, 820)], C["buz"])
resistor_h(580, 700, 820, "R6 1 kΩ", C["buz"])
wire([(700, 820), (764, 820)], C["buz"])
text(470, 812, "BUZZER", 12, color=C["buz"], weight="bold")
npn(784, 820)
wire([(794, 800), (794, 770)], C["buz"])
add('<rect x="772" y="722" width="44" height="40" rx="6" fill="#333"/>')
text(794, 747, "BZ", 13, "middle", "bold", "#fff")
text(822, 738, "active buzzer 5V", 11.5, color="#555")
text(822, 754, "(+ to 5V, − to Q1 C)", 11.5, color="#555")
wire([(794, 770), (794, 762)], C["buz"])
wire([(794, 722), (794, 708)], C["5v"]); supply(794, 708, "5V", C["5v"], lead=10)
wire([(794, 840), (794, 856)], C["gnd"]); ground(794, 856, lead=4)

# ------------------------------------------------------------------ LEDs
for y, color, gpio_name, name in ((900, C["red"], "RED LED", "red LED (fire / warning)"),
                                  (960, C["green"], "GREEN LED", "green LED (system safe)")):
    wire([(PI_R, y), (580, y)], color)
    resistor_h(580, 680, y, "330 Ω", color)
    wire([(680, y), (720, y)], color)
    led_h(720, y, color, "")
    wire([(742, y), (800, y)], C["gnd"]); ground(800, y, lead=8)
    text(470, y - 8, gpio_name, 12, color=color, weight="bold")
    text(830, y + 5, name, 12, color="#555")

# ------------------------------------------------------------------ camera
add(f'<rect x="170" y="1000" width="60" height="70" fill="#d9d9d9" stroke="#888" stroke-width="1.5"/>')
text(240, 1030, "15-pin CSI ribbon cable", 12, color="#555")
text(240, 1046, "(\"CAMERA\" port, blue side towards the USB/Ethernet ports)", 11, color="#777")
box(110, 1070, 230, 90, "Pi Camera Module 3 / v2", "8 / 12 MP, CSI interface", fill="#eef2ff")
add('<circle cx="225" cy="1138" r="11" fill="#222"/><circle cx="225" cy="1138" r="5" fill="#556"/>')

# ------------------------------------------------------------------ legend / notes
LX, LY = 1000, 790
add(f'<rect x="{LX}" y="{LY}" width="430" height="390" rx="10" fill="#fffdf5" stroke="#c9a227" stroke-width="1.5"/>')
text(LX + 16, LY + 28, "Notes", 16, weight="bold")
notes = [
    "• Flags with the same name (3V3, 5V, GND ⏚) are the same wire.",
    "• Crossing wires without a dot are NOT connected.",
    "• Pi GPIO pins are 3.3 V only - never feed them 5 V.",
    "  MQ-2 runs on 5 V, so both of its outputs pass through",
    "  a 10 kΩ / 20 kΩ divider:  5 V × 20/(10+20) = 3.33 V.",
    "• The Pi has no analog input: the ADS1115 converts MQ-2",
    "  AO to a number over I2C (enable I2C in raspi-config).",
    "• Many DHT22 breakout boards already have the 10 kΩ",
    "  pull-up (R1) - then skip R1.",
    "• Q1 lets a 3.3 V GPIO switch the 5 V buzzer current.",
    "  Use an ACTIVE buzzer (beeps on DC), not a passive one.",
    "• MQ-2 heater: burn in 24 h before first calibration;",
    "  wait ~3 min after each power-up for stable readings.",
    "• Wire colours: orange 3V3 · red 5V · black GND · yellow",
    "  DHT · blue SDA · teal SCL · purple DO · brown AO.",
]
for i, line in enumerate(notes):
    text(LX + 16, LY + 56 + i * 21, line.replace("  ", "\u00a0\u00a0\u00a0"), 12.5, color="#333")

add("</svg>")

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT}")
