import machine
import ubinascii
import network

# === Define GPIO Pins for Role & ID Assignment ===
role_pins = [
    machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_DOWN), 
    machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_DOWN),
    machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN),
    ]
id_pins = [machine.Pin(4, machine.Pin.IN), machine.Pin(16, machine.Pin.IN), machine.Pin(17, machine.Pin.IN), machine.Pin(5, machine.Pin.IN)]

# === Read Device Role from GPIO ===
role_value = (
    (role_pins[0].value() << 2) | 
    (role_pins[1].value() << 1) |
     role_pins[2].value()
)
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER", 3: "TELEMETRY"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

# === Read Unique Device ID from GPIO ===
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# === Get Base MAC Address ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
esp_mac = ubinascii.hexlify(wlan.config('mac'), ':').decode()

# === Assign MAC Prefix Based on Device Type ===
mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02", "TELEMETRY": "AC:DB:03"}
expected_mac = f"{mac_prefix[DEVICE_TYPE]}:{device_id:02X}:{device_id:02X}"

# === Print Debugging Information ===
print("\n=== GPIO ROLE & ID VERIFICATION ===")
print(f"Device Role: {DEVICE_TYPE}")
print(f"Device ID: {device_id}")
print(f"Generated MAC: {expected_mac}")
print(f"Actual MAC: {esp_mac}")
print("==================================\n")

# === Error Handling ===
if DEVICE_TYPE == "UNKNOWN":
    print("[ERROR] Invalid role configuration! Check GPIO wiring for role selection.")
    print("[INFO] Ensure GPIO18 & GPIO19 are correctly wired for role selection.")
elif device_id == 0:
    print("[WARNING] Device ID is 0. Verify GPIO4, GPI16, GPIO17, and GPIO5 connections.")

print("[INFO] If all values are correct, proceed with ESP-NOW communication.")


# Flash: mpremote connect /dev/ttyUSB0 fs cp gpio_test.py :
# mpremote connect /dev/ttyUSB0 exec "import gpio_test"
