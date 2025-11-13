#Telemetry Test
from machine import Pin, I2C, ADC
import time
from sh1106 import SH1106_I2C

# -----------------------------------------------------
# I²C SETUP (OLED + ADXL345)
# -----------------------------------------------------
i2c = I2C(0,
          scl=Pin(22, Pin.OPEN_DRAIN, Pin.PULL_UP),
          sda=Pin(21, Pin.OPEN_DRAIN, Pin.PULL_UP),
          freq=400000)

ADXL345_ADDR = 0x53
OLED_ADDR = 0x3C

# -----------------------------------------------------
# OLED DISPLAY
# -----------------------------------------------------
oled = SH1106_I2C(128, 32, i2c, addr=OLED_ADDR)

# -----------------------------------------------------
# LM35 TEMPERATURE SENSOR (Analog)
# -----------------------------------------------------
lm35 = ADC(Pin(34))
lm35.atten(ADC.ATTN_11DB)
lm35.width(ADC.WIDTH_12BIT)

# -----------------------------------------------------
# ADXL345 FUNCTIONS
# -----------------------------------------------------
def adxl345_init():
    try:
        i2c.writeto_mem(ADXL345_ADDR, 0x2D, b'\x08')  # Measurement mode
        return True
    except:
        return False

def adxl345_read():
    try:
        data = i2c.readfrom_mem(ADXL345_ADDR, 0x32, 6)
        x = int.from_bytes(data[0:2], 'little', signed=True) * 0.004
        y = int.from_bytes(data[2:4], 'little', signed=True) * 0.004
        z = int.from_bytes(data[4:6], 'little', signed=True) * 0.004
        return (x, y, z)
    except:
        return (None, None, None)

adxl_ok = adxl345_init()

# -----------------------------------------------------
# DRAWING HELPERS
# -----------------------------------------------------
def draw_temp_bar(temp_c):
    """Draw temperature bar (0–50°C range)."""
    bar_length = int((temp_c / 50) * 120)
    if bar_length < 0: bar_length = 0
    if bar_length > 120: bar_length = 120

    oled.text("Temp: {:.1f}C".format(temp_c), 0, 0)
    oled.rect(4, 12, 120, 10, 1)           # Outline
    oled.fill_rect(4, 12, bar_length, 10, 1)  # Filled portion

def draw_tilt_cross(xg, yg):
    """Draw crosshair showing tilt direction."""
    cx, cy = 64, 50  # Center
    scale = 10       # Scale factor for motion
    if xg is None or yg is None:
        oled.text("No accel data", 20, 48)
        return

    px = int(cx + xg * scale)
    py = int(cy - yg * scale)
    # Clamp to screen bounds
    px = max(0, min(px, 127))
    py = max(30, min(py, 63))

    oled.text("Tilt", 0, 35)
    oled.hline(0, cy, 128, 1)
    oled.vline(cx, 30, 34, 1)
    oled.fill_rect(px - 1, py - 1, 3, 3, 1)

# -----------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------
while True:
    # ---- Read temperature ----
    raw = lm35.read()
    voltage = raw * (3.3 / 4095)
    temp_c = voltage * 100.0
    temp_f = (temp_c * 9 / 5) + 32

    # ---- Read accelerometer ----
    xg, yg, zg = adxl345_read()

    # ---- OLED Rendering ----
    oled.fill(0)
    draw_temp_bar(temp_c)
    draw_tilt_cross(xg, yg)
    oled.show()

    # ---- Serial Debug ----
    if xg is not None:
        print("Temp={:.1f}C ({:.1f}F) | X={:+.2f}g Y={:+.2f}g Z={:+.2f}g".format(
            temp_c, temp_f, xg, yg, zg))
    else:
        print("Temp={:.1f}C | ADXL345 not responding".format(temp_c))

    time.sleep(0.5)