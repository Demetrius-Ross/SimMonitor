from machine import Pin, I2C, ADC
import time
from ssd1306 import SSD1306_I2C

# --------------------------------------
# I2C setup (OLED + ADXL345)
# --------------------------------------
i2c = I2C(
    0,
    scl=Pin(22, Pin.OPEN_DRAIN, Pin.PULL_UP),
    sda=Pin(21, Pin.OPEN_DRAIN, Pin.PULL_UP),
    freq=400000
)

print("I2C scan:", i2c.scan())   # should show [60]

# OLED 128x32
oled = SSD1306_I2C(128, 32, i2c, addr=0x3C)

# --------------------------------------
# LM35 Temperature Sensor
# --------------------------------------
lm35 = ADC(Pin(34))
lm35.atten(ADC.ATTN_11DB)   # 0–3.3V
lm35.width(ADC.WIDTH_12BIT)


# --------------------------------------
# ADXL345 Accelerometer
# --------------------------------------
ADXL345_ADDR = 0x53

def adxl_init():
    try:
        i2c.writeto_mem(ADXL345_ADDR, 0x2D, b'\x08')
        return True
    except:
        return False

def adxl_read():
    try:
        data = i2c.readfrom_mem(ADXL345_ADDR, 0x32, 6)
        x = int.from_bytes(data[0:2], 'little', signed=True) * 0.004
        y = int.from_bytes(data[2:4], 'little', signed=True) * 0.004
        z = int.from_bytes(data[4:6], 'little', signed=True) * 0.004
        return x, y, z
    except:
        return None, None, None

adxl_ok = adxl_init()


# --------------------------------------
# MAIN LOOP
# --------------------------------------
while True:

    # ---- TEMPERATURE ----
    raw = lm35.read()

    voltage = (raw * 3.3) / 4095

    temp_c = voltage * 100.0

    # clamp negative noise
    if temp_c < 0:
        temp_c = 0

    # ---- ACCELEROMETER ----
    xg, yg, zg = adxl_read()

    # ---- OLED OUTPUT ----
    oled.fill(0)
    oled.text("Temp:{:.1f}C".format(temp_c), 0, 0)

    if xg is not None:
        oled.text("X:{:+.2f}".format(xg), 0, 12)
        oled.text("Y:{:+.2f}".format(yg), 64, 12)
    else:
        oled.text("ADXL ERR", 0, 12)

    oled.show()

    # ---- SERIAL OUTPUT ----
    print("Temp {:.1f}C | X={:+.2f} Y={:+.2f} Z={:+.2f}".format(
        temp_c, xg if xg else 0, yg if yg else 0, zg if zg else 0)
    )

    time.sleep(0.3)