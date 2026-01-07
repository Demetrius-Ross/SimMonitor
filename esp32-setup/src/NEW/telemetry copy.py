from machine import Pin, I2C
import time
import math

# ========= ADXL345 CONSTANTS =========
ADXL345_ADDR = 0x53  # SDO → GND

REG_DEVID       = 0x00
REG_BW_RATE     = 0x2C
REG_POWER_CTL   = 0x2D
REG_DATA_FORMAT = 0x31
REG_DATAX0      = 0x32
REG_INT_ENABLE  = 0x2E
REG_INT_MAP     = 0x2F
REG_INT_SOURCE  = 0x30


class ADXL345:
    def __init__(self, i2c, addr=ADXL345_ADDR):
        self.i2c = i2c
        self.addr = addr

        devid = self.read_reg(REG_DEVID)
        print("ADXL345 DEVID: 0x{:02X}".format(devid))
        if devid != 0xE5:
            print("WARNING: ADXL345 not detected (DEVID != 0xE5)")

        # 100 Hz output
        self.write_reg(REG_BW_RATE, 0x0A)

        # Full resolution ±2g
        self.write_reg(REG_DATA_FORMAT, 0x08)

        # Measurement mode
        self.write_reg(REG_POWER_CTL, 0x08)

        print("ADXL345 initialization complete.\n")

    def write_reg(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def read_reg(self, reg):
        return int.from_bytes(self.i2c.readfrom_mem(self.addr, reg, 1), "little")

    # --- XYZ reading with manual signed conversion ---
    def read_xyz_raw(self):
        data = self.i2c.readfrom_mem(self.addr, REG_DATAX0, 6)

        def to_int16(lo, hi):
            v = lo | (hi << 8)
            if v & 0x8000:
                v -= 65536
            return v

        x = to_int16(data[0], data[1])
        y = to_int16(data[2], data[3])
        z = to_int16(data[4], data[5])

        return x, y, z

    def read_xyz_g(self):
        x_raw, y_raw, z_raw = self.read_xyz_raw()
        scale = 0.0039
        return x_raw * scale, y_raw * scale, z_raw * scale

    # --- Pitch / Roll / Tilt ---
    def compute_angles(self):
        x, y, z = self.read_xyz_g()
        norm = math.sqrt(x*x + y*y + z*z)

        if norm == 0:
            return 0, 0, 0

        roll  = math.atan2(y, z)
        pitch = math.atan2(-x, math.sqrt(y*y + z*z))
        tilt  = math.acos(z / norm)

        return math.degrees(roll), math.degrees(pitch), math.degrees(tilt)


# ========= FIXED PIN ASSIGNMENTS =========
SDA_PIN  = 21
SCL_PIN  = 22
INT1_PIN = 18
INT2_PIN = 19

print("Using fixed pins:")
print("  SDA =", SDA_PIN)
print("  SCL =", SCL_PIN)
print("  INT1 =", INT1_PIN)
print("  INT2 =", INT2_PIN)
print()

# ========= SETUP I2C =========
i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400_000)
adxl = ADXL345(i2c)

# ========= INTERRUPT SETUP =========
def int1_handler(pin):
    print("INT1 interrupt")

def int2_handler(pin):
    print("INT2 interrupt")

int1 = Pin(INT1_PIN, Pin.IN, Pin.PULL_UP)
int2 = Pin(INT2_PIN, Pin.IN, Pin.PULL_UP)

int1.irq(trigger=Pin.IRQ_FALLING, handler=int1_handler)
int2.irq(trigger=Pin.IRQ_FALLING, handler=int2_handler)

print("Starting main loop...\n")

# ========= MAIN LOOP =========
while True:
    x_g, y_g, z_g = adxl.read_xyz_g()
    roll, pitch, tilt = adxl.compute_angles()

    print("X={:.3f}g  Y={:.3f}g  Z={:.3f}g".format(x_g, y_g, z_g))
    print("Roll={:.2f}°  Pitch={:.2f}°  Tilt={:.2f}°".format(roll, pitch, tilt))
    print()

    time.sleep(0.2)
