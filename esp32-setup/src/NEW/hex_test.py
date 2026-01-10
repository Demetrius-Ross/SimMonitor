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



def stable_read(pin, samples=15, delay_ms=2):
    s = 0
    for _ in range(samples):
        s += pin.value()
        time.sleep_ms(delay_ms)
    return 1 if s > (samples // 2) else 0
    
    
    
A = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
B = machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN)
C = machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN)
D = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)

time.sleep_ms(200)  # give strapping pins + switch network time to settle

a = stable_read(A)
b = stable_read(B)
c = stable_read(C)
d = stable_read(D)

raw_id = (a << 3) | (b << 2) | (c << 1) | d
device_id = raw_id ^ 0x0F

print("ID pins (17,5,4,16) =", a, b, c, d, "raw=0x{:X} id={}".format(raw_id, device_id))
    