import machine
import ubinascii
import network
import time

role_pins = [
    machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_DOWN),
    machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_DOWN),
    machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN),
]

time.sleep_ms(50)

role_value = (
    (role_pins[0].value() << 2) |
    (role_pins[1].value() << 1) |
     role_pins[2].value()
)

roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER", 3: "TELEMETRY"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

id_pins = {
    1: machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN),
    2: machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN),
    4: machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN),
    8: machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN),
}

raw_id = 0
for weight, pin in id_pins.items():
    if pin.value():
        raw_id |= weight

device_id = raw_id ^ 0x0F

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
esp_mac = ubinascii.hexlify(wlan.config('mac'), ':').decode()

mac_prefix = {
    "SENDER": "AC:DB:00",
    "RELAY": "AC:DB:01",
    "RECEIVER": "AC:DB:02",
    "TELEMETRY": "AC:DB:03"
}

virtual_mac = f"{mac_prefix.get(DEVICE_TYPE, 'AC:DB:FF')}:{device_id:02X}:{device_id:02X}"

print("\n=== GPIO ROLE & ID VERIFICATION ===")
print(f"Role Pins (19,18,14): {role_pins[0].value()} {role_pins[1].value()} {role_pins[2].value()}")
print(f"Device Role          : {DEVICE_TYPE}")
print(f"Raw ID               : 0x{raw_id:X}")
print(f"Corrected Device ID  : {device_id}")
print(f"Generated Virtual MAC: {virtual_mac}")
print(f"Actual ESP32 MAC     : {esp_mac}")
print("==================================\n")

if DEVICE_TYPE == "UNKNOWN":
    print("[ERROR] Invalid role configuration.")
elif device_id < 0 or device_id > 15:
    print("[ERROR] Invalid device ID.")
else:
    print("[OK] GPIO configuration is valid.")