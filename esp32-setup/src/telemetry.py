from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import onewire, ds18x20
import time

# =========================================
# I2C SETUP (OLED + ADXL345)
# =========================================
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
print("I2C scan:", i2c.scan())

# OLED 128x32
oled = SSD1306_I2C(128, 32, i2c, addr=0x3C)

# =========================================
# ADXL345 ACCELEROMETER
# =========================================
ADXL345_ADDR = 0x53

def adxl_init():
    try:
        i2c.writeto_mem(ADXL345_ADDR, 0x2D, b'\x08')   # enable measurement mode
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

# =========================================
# DS18B20 TEMPERATURE SENSOR
# =========================================
TEMP_PIN = 19
dat = Pin(TEMP_PIN)
ow = onewire.OneWire(dat)
ds = ds18x20.DS18X20(ow)

roms = ds.scan()
print("DS18B20 devices found:", roms)

has_temp_sensor = len(roms) > 0
if not has_temp_sensor:
    print("ERROR: No DS18B20 sensors found!")

# =========================================
# MAIN LOOP
# =========================================
while True:

    # ---- Temperature (DS18B20) ----
    if has_temp_sensor:
        ds.convert_temp()
        time.sleep_ms(750)

        try:
            temp_c = ds.read_temp(roms[0])
            temp_f = temp_c * 9/5 + 32
            temp_str = "{:.1f}C".format(temp_c)
        except:
            temp_str = "ERR"
            temp_c = None
    else:
        temp_str = "NO T"
        temp_c = None

    # ---- Accelerometer ----
    xg, yg, zg = adxl_read()

    # ---- OLED DISPLAY ----
    oled.fill(0)
    oled.text("T: {}".format(temp_str), 0, 0)     # line 1 temp

    if xg is not None:
        oled.text("X:{:+.2f}".format(xg), 0, 12)
        oled.text("Y:{:+.2f}".format(yg), 64, 12)
    else:
        oled.text("ADXL ERR", 0, 12)

    oled.show()

    # ---- Serial Output ----
    if temp_c is not None:
        print("Temp: {:.2f}C / {:.2f}F".format(temp_c, temp_f))
    else:
        print("Temp sensor error")

    if xg is not None:
        print("Accel: X={:+.2f} Y={:+.2f} Z={:+.2f}".format(xg, yg, zg))
    else:
        print("Accel read error")

    print("----")
    time.sleep(0.5)