import machine
import time

pins = {
    "GPIO17": machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN),
    "GPIO5":  machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN),
    "GPIO4":  machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN),
    "GPIO16": machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN),
}

while True:
    states = []
    for name, pin in pins.items():
        states.append("{}={}".format(name, pin.value()))
    print(" | ".join(states))
    time.sleep(1)
    
    fixed = (
    ((raw_id & 0b0001) << 1) |  # bit0 → bit1
    ((raw_id & 0b0010) >> 1) |  # bit1 → bit0
    ((raw_id & 0b0100) << 1) |  # bit2 → bit3
    ((raw_id & 0b1000) >> 1)    # bit3 → bit2
)
    