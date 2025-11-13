from machine import Pin, I2C, ADC
from ssd1306 import SSD1306_I2C
import math, time

# =====================================
# I2C (OLED + ADXL345)
# =====================================
i2c = I2C(
    0,
    scl=Pin(22, Pin.OPEN_DRAIN, Pin.PULL_UP),
    sda=Pin(21, Pin.OPEN_DRAIN, Pin.PULL_UP),
    freq=400000
)

print("I2C scan:", i2c.scan())   # should show [60, 83]

oled = SSD1306_I2C(128, 32, i2c, addr=0x3C)

# =====================================
# ADXL345 Accelerometer
# =====================================
ADXL345_ADDR = 0x53

def adxl_init():
    try:
        # Power on
        i2c.writeto_mem(ADXL345_ADDR, 0x2D, b'\x08')
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
# ANALOG THERMISTOR (KEYES DS18B20 MODULE)
# =====================================

# Use ADC1 pin only (WiFi safe)
adc = ADC(Pin(34))
adc.atten(ADC.ATTN_11DB)
adc.width(ADC.WIDTH_12BIT)

# Thermistor parameters (KEYES 10k NTC)
Beta = 3950
R0 = 10000       # 10k thermistor at 25°C
T0 = 298.15      # 25°C in Kelvin
R_fixed = 10000  # Board’s fixed resistor

def read_temperature():
    raw = adc.read()
    V = (raw / 4095.0) * 3.3

    # Avoid division by zero
    if V < 0.05 or V > 3.25:
        return None

    # Thermistor resistance
    Rt = R_fixed * (V / (3.3 - V))

    # Beta formula
    tempK = 1 / (1/T0 + (1/Beta) * math.log(Rt / R0))
    tempC = tempK - 273.15

    return tempC

# =====================================
# MAIN LOOP
# =====================================
while True:

    # ---- Temperature ----
    temp = read_temperature()

    # ---- Accelerometer ----
    xg, yg, zg = adxl_read()

    # ---- OLED ----
    oled.fill(0)

    if temp is not None:
        oled.text("T:{:.1f}C".format(temp), 0, 0)
    else:
        oled.text("T: ERR", 0, 0)

    if xg is not None:
        oled.text("X:{:+.2f}".format(xg), 0, 12)
        oled.text("Y:{:+.2f}".format(yg), 64, 12)
    else:
        oled.text("ADXL ERR", 0, 12)

    oled.show()

    # ---- Serial Debug ----
    if temp is not None and xg is not None:
        print("Temp:{:.1f}C  X={:+.2f}  Y={:+.2f}  Z={:+.2f}".format(temp, xg, yg, zg))
    elif temp is None:
        print("Temperature read error")
    else:
        print("Accelerometer error")

    time.sleep(0.2)