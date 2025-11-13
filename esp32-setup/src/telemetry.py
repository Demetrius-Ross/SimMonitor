from machine import Pin, I2C, ADC
from ssd1306 import SSD1306_I2C
import time

# =====================================
# I2C (OLED + ADXL345)
# =====================================
i2c = I2C(
    0,
    scl=Pin(22, Pin.OPEN_DRAIN, Pin.PULL_UP),
    sda=Pin(21, Pin.OPEN_DRAIN, Pin.PULL_UP),
    freq=400000
)

print("I2C scan:", i2c.scan())   # expect [60, 83] or similar

# OLED 128x32 @ 0x3C
oled = SSD1306_I2C(128, 32, i2c, addr=0x3C)

# =====================================
# ADXL345 Accelerometer
# =====================================
ADXL345_ADDR = 0x53

def adxl_init():
    try:
        i2c.writeto_mem(ADXL345_ADDR, 0x2D, b'\x08')  # measurement mode
        return True
    except Exception as e:
        print("ADXL init error:", e)
        return False

def adxl_read():
    try:
        data = i2c.readfrom_mem(ADXL345_ADDR, 0x32, 6)
        x = int.from_bytes(data[0:2], 'little', signed=True) * 0.004
        y = int.from_bytes(data[2:4], 'little', signed=True) * 0.004
        z = int.from_bytes(data[4:6], 'little', signed=True) * 0.004
        return x, y, z
    except Exception as e:
        print("ADXL read error:", e)
        return None, None, None

adxl_ok = adxl_init()

# =====================================
# LM35 Temperature Sensor (analog)
# =====================================
lm35 = ADC(Pin(34))
lm35.atten(ADC.ATTN_11DB)      # 0–3.3V range
lm35.width(ADC.WIDTH_12BIT)   # 0–4095

def read_temp_c():
    # simple 4-sample average for stability
    acc = 0
    for _ in range(4):
        acc += lm35.read()
        time.sleep_ms(5)
    raw = acc / 4.0

    voltage = (raw / 4095.0) * 3.3     # ADC ref = 3.3V
    temp_c = voltage * 100.0           # LM35 = 10mV/°C

    return temp_c

# =====================================
# MAIN LOOP
# =====================================
while True:
    # ---- Temperature ----
    temp_c = read_temp_c()
    temp_f = temp_c * 9.0 / 5.0 + 32.0

    # ---- Accelerometer ----
    xg, yg, zg = adxl_read()

    # ---- OLED ----
    oled.fill(0)
    oled.text("T:{:.1f}C".format(temp_c), 0, 0)   # line 1
    # Show accel or error
    if xg is not None:
        oled.text("X:{:+.2f}".format(xg), 0, 12)
        oled.text("Y:{:+.2f}".format(yg), 64, 12)
    else:
        oled.text("ADXL ERR", 0, 12)

    oled.show()

    # ---- Serial debug ----
    if xg is not None:
        print("T={:.1f}C ({:.1f}F) | X={:+.2f} Y={:+.2f} Z={:+.2f}".format(
            temp_c, temp_f, xg, yg, zg))
    else:
        print("T={:.1f}C ({:.1f}F) | ADXL error".format(temp_c, temp_f))

    time.sleep(0.5)