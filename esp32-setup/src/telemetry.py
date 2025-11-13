import machine
import onewire
import ds18x20
import time

# ====== CONFIG ======
DATA_PIN = 19   # change to your pin if needed

# Setup OneWire bus
dat = machine.Pin(DATA_PIN)
ow = onewire.OneWire(dat)

# Setup DS18B20 driver
ds = ds18x20.DS18X20(ow)

# Scan for devices
roms = ds.scan()
print("Found DS18B20 devices:", roms)

if not roms:
    print("ERROR: No sensors found. Check wiring.")
    while True:
        time.sleep(1)  # stop program

# Read temperature loop
while True:
    ds.convert_temp()       # start temperature conversion
    time.sleep_ms(750)      # wait for conversion to finish

    for rom in roms:
        temp_c = ds.read_temp(rom)
        temp_f = temp_c * 9/5 + 32

        print("Sensor:", rom)
        print("  Temperature: {:.2f} °C  |  {:.2f} °F".format(temp_c, temp_f))
    
    print()
    time.sleep(1)
