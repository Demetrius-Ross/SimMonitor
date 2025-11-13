from machine import Pin, I2C
import time
import math
import onewire
import ds18x20
import ssd1306

# ========== OLED SETUP ==========
OLED_WIDTH  = 128
OLED_HEIGHT = 32
SDA_PIN  = 21
SCL_PIN  = 22

i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400_000)
devices = i2c.scan()
print("I2C scan:", devices)

if 0x3C not in devices:
    print("ERROR: OLED not found!")
else:
    print("OLED detected at 0x3C")

oled = ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)

# Clear screen safely
def oled_print(lines):
    oled.fill(0)
    y = 0
    for line in lines:
        oled.text(line, 0, y)
        y += 12
    oled.show()


# ========== DS18B20 SETUP ==========
TEMP_PIN = 19
ow = onewire.OneWire(Pin(TEMP_PIN))
ds = ds18x20.DS18X20(ow)
roms = ds.scan()
print("DS18B20 ROMs:", roms)

if not roms:
    raise RuntimeError("No DS18B20 temperature sensors found!")


# ========== ADXL345 CONSTANTS ==========
ADXL345_ADDR = 0x53
REG_DEVID       = 0x00
REG_BW_RATE     = 0x2C
REG_POWER_CTL   = 0x2D
REG_DATA_FORMAT = 0x31
REG_DATAX0      = 0x32
REG_INT_ENABLE  = 0x2E
REG_INT_MAP     = 0x2F
REG_INT_SOURCE  = 0x30


# ========== ADXL345 DRIVER ==========
class ADXL345:
    def __init__(self, i2c, addr=ADXL345_ADDR):
        self.i2c = i2c
        self.addr = addr

        devid = self.read_reg(REG_DEVID)
        print("ADXL345 DEVID: 0x{:02X}".format(devid))
        if devid != 0xE5:
            print("WARNING: ADXL345 not detected")

        self.write_reg(REG_BW_RATE, 0x0A)        # 100 Hz
        self.write_reg(REG_DATA_FORMAT, 0x08)    # FULL_RES, ±2g
        self.write_reg(REG_POWER_CTL, 0x08)      # Measure mode

        print("ADXL345 ready.\n")

    def write_reg(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def read_reg(self, reg):
        return int.from_bytes(self.i2c.readfrom_mem(self.addr, reg, 1), "little")

    def read_xyz_raw(self):
        data = self.i2c.readfrom_mem(self.addr, REG_DATAX0, 6)

        def s16(lo, hi):
            v = lo | (hi << 8)
            return v - 65536 if v & 0x8000 else v

        x = s16(data[0], data[1])
        y = s16(data[2], data[3])
        z = s16(data[4], data[5])
        return x, y, z

    def read_xyz_g(self):
        x, y, z = self.read_xyz_raw()
        scale = 0.0039
        return x * scale, y * scale, z * scale

    def compute_angles(self):
        x, y, z = self.read_xyz_g()
        norm = math.sqrt(x*x + y*y + z*z)
        if norm == 0:
            return 0, 0, 0

        roll  = math.atan2(y, z)
        pitch = math.atan2(-x, math.sqrt(y*y + z*z))
        tilt  = math.acos(z / norm)
        return math.degrees(roll), math.degrees(pitch), math.degrees(tilt)


# ========== ACCELEROMETER & INTERRUPTS ==========
INT1_PIN = 18
INT2_PIN = 5  # <— safer, since DS18B20 uses 19

int1 = Pin(INT1_PIN, Pin.IN, Pin.PULL_UP)
int2 = Pin(INT2_PIN, Pin.IN, Pin.PULL_UP)

def int1_handler(pin):
    print("[INT1] Accelerometer interrupt!")

def int2_handler(pin):
    print("[INT2] Accelerometer interrupt!")

int1.irq(trigger=Pin.IRQ_FALLING, handler=int1_handler)
int2.irq(trigger=Pin.IRQ_FALLING, handler=int2_handler)

adxl = ADXL345(i2c)


# ========== MAIN LOOP ==========
while True:
    # --- Temperature ---
    ds.convert_temp()
    time.sleep_ms(750)

    try:
        temp_c = ds.read_temp(roms[0])
        temp_f = temp_c * 9/5 + 32
    except:
        temp_c = None
        temp_f = None

    # --- Accelerometer ---
    xg, yg, zg = adxl.read_xyz_g()
    roll, pitch, tilt = adxl.compute_angles()

    # SERIAL PRINT
    print("\n=== SENSOR DATA ===")
    print("Temp: {:.2f}C  {:.2f}F".format(temp_c, temp_f))
    print("Acc: X={:.2f}g  Y={:.2f}g  Z={:.2f}g".format(xg, yg, zg))
    print("Angles: Roll={:.1f}° Pitch={:.1f}° Tilt={:.1f}°".format(
        roll, pitch, tilt
    ))

    # OLED DISPLAY
    oled_print([
        "T: {:.1f}C / {:.1f}F".format(temp_c, temp_f),
        "X:{:.2f}g Y:{:.2f}g".format(xg, yg),
        "Z:{:.2f}g".format(zg),
        "R:{:.1f} P:{:.1f}".format(roll, pitch),
        "Tilt:{:.1f}deg".format(tilt)
    ])

    time.sleep(0.2)