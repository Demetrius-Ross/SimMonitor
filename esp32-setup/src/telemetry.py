from machine import Pin, I2C
import time

# ===== ADXL345 I2C address =====
ADXL345_ADDR = 0x53  # assuming SDO → GND

# ===== Registers =====
REG_DEVID       = 0x00
REG_BW_RATE     = 0x2C
REG_POWER_CTL   = 0x2D
REG_DATA_FORMAT = 0x31
REG_DATAX0      = 0x32


class ADXL345:
    def __init__(self, i2c, addr=ADXL345_ADDR):
        self.i2c = i2c
        self.addr = addr

        # Check device ID
        devid = self.read_reg(REG_DEVID)
        print("ADXL345 DEVID: 0x{:02X}".format(devid))
        if devid != 0xE5:
            print("WARNING: ADXL345 not detected (DEVID != 0xE5)")

        # Set data rate: 100 Hz (0x0A)
        self.write_reg(REG_BW_RATE, 0x0A)

        # Data format:
        #  FULL_RES = 1 (bit 3)
        #  Range = ±2g (bits 1:0 = 0)
        #  => 0b00001000 = 0x08
        self.write_reg(REG_DATA_FORMAT, 0x08)

        # Power control: Measure mode (bit 3 = 1)
        self.write_reg(REG_POWER_CTL, 0x08)

    def write_reg(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def read_reg(self, reg):
        return int.from_bytes(self.i2c.readfrom_mem(self.addr, reg, 1), "little")

    def read_xyz_raw(self):
        # Read 6 bytes starting at DATAX0
        data = self.i2c.readfrom_mem(self.addr, REG_DATAX0, 6)
        # Little-endian signed 16-bit values
        x = int.from_bytes(data[0:2], "little", signed=True)
        y = int.from_bytes(data[2:4], "little", signed=True)
        z = int.from_bytes(data[4:6], "little", signed=True)
        return x, y, z

    def read_xyz_g(self):
        x_raw, y_raw, z_raw = self.read_xyz_raw()
        # FULL_RES mode scale factor ~3.9 mg/LSB at ±2g
        scale = 0.0039  # g per LSB
        x_g = x_raw * scale
        y_g = y_raw * scale
        z_g = z_raw * scale
        return x_g, y_g, z_g


# ===== SETUP I2C & SENSOR =====

# ESP32 default I2C pins: SDA=21, SCL=22
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400_000)

adxl = ADXL345(i2c)

print("Starting ADXL345 read loop...")

while True:
    x_g, y_g, z_g = adxl.read_xyz_g()
    x_raw, y_raw, z_raw = adxl.read_xyz_raw()

    print("X: {:.3f} g  |  Y: {:.3f} g  |  Z: {:.3f} g".format(x_g, y_g, z_g))
    print("   raw: x={}, y={}, z={}".format(x_raw, y_raw, z_raw))
    print()
    time.sleep(0.2)
