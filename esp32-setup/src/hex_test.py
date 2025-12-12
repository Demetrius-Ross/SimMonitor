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