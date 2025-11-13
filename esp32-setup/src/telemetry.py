from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import onewire, ds18x20
import time

# =========================================
# I2C SETUP
# =========================================
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
print("I2C scan:", i2c.scan())

# =========================================
# OLED DISPLAY (128x32)
# =========================================
oled = SSD1306_I2C(128, 32, i2c, addr=0x3C)

# =========================================
# ADXL345 CLASS (Your Updated Version)
# =========================================
ADXL345_ADDR = 0x53

REG_DEVID       = 0x00
REG_BW_RATE     = 0x2C
REG_POWER_CTL   = 0x2D
REG_DATA_FORMAT = 0x31
REG_DATAX0      = 0x32

class ADXL345:
    def __init__(self, i2c, addr=ADXL345_ADDR):
        self.i2c = i2c
        self.addr = addr

        devid = self.read_reg(REG_DEVID)
        print("ADXL345 DEVID: 0x{:02X}".format(devid))
        if devid != 0xE5:
            print("WARNING: ADXL345 not detected (DEVID != 0xE5)")

        self.write_reg(REG_BW_RATE, 0x0A)      # 100 Hz
        self.write_reg(REG_DATA_FORMAT, 0x08)  # FULL_RES ±2g
        self.write_reg(REG_POWER_CTL, 0x08)    # Measure mode

    def write_reg(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def read_reg(self, reg):
        return int.from_bytes(self.i2c.readfrom_mem(self.addr, reg, 1), "little")

    def read_xyz_raw(self):
        data = self.i2c.readfrom_mem(self.addr, REG_DATAX0, 6)
        x = int.from_bytes(data[0:2], "little", signed=True)
        y = int.from_bytes(data[2:4], "little", signed=True)
        z = int.from_bytes(data[4:6], "little", signed=True)
        return x, y, z

    def read_xyz_g(self):
        x_raw, y_raw, z_raw = self.read_xyz_raw()
        scale = 0.0039  # g/LSB (FULL-RES)
        return x_raw * scale, y_raw * scale, z_raw * scale

# Create ADXL object
adxl = ADXL345(i2c)

# =========================================
# DS18B20 DIGITAL TEMPERATURE SENSOR
# =========================================
TEMP_PIN = 19
ow = onewire.OneWire(Pin(TEMP_PIN))
ds = ds18x20.DS18X20(ow)
roms = ds.scan()

if roms:
    print("DS18B20 found:", roms)
    has_temp = True
else:
    print("ERROR: No DS18B20 detected!")
    has_temp = False

# =========================================
# MAIN LOOP
# =========================================
while True:

    # ---- Read DS18B20 ----
    if has_temp:
        ds.convert_temp()
        time.sleep_ms(750)

        try:
            c = ds.read_temp(roms[0])
            f = c * 9/5 + 32
            temp_text = "{:.1f}C".format(c)
            temp_text_f = "{:.1f}F".format(f)
        except:
            c = None
            temp_text = "ERR"
    else:
        temp_text = "NO T"
        c = None

    # ---- Read Accelerometer ----
    try:
        xg, yg, zg = adxl.read_xyz_g()
    except:
        xg = yg = zg = None

    # ---- OLED OUTPUT ----
    oled.fill(0)
    oled.text("T: {}".format(temp_text), 0, 0)
    oled.text("T: {}".format(temp_text_f), 64, 0)

    if xg is not None:
        oled.text("X:{:+.2f}".format(xg), 0, 12)
        oled.text("Y:{:+.2f}".format(yg), 64, 12)
    else:
        oled.text("ADXL ERR", 0, 12)

    oled.show()

    # ---- SERIAL OUTPUT ----
    print("---- SENSOR DATA ----")

    if c is not None:
        print("Temp: {:.2f}C  {:.2f}F".format(c, f))
    else:
        print("Temp read error")

    if xg is not None:
        print("Accel g: X={:+.3f} Y={:+.3f} Z={:+.3f}".format(xg, yg, zg))
    else:
        print("Accel read error")

    print("---------------------\n")

    time.sleep(0.3)