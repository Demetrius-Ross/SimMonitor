import machine
import time

# Define GPIOs for role identification
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]

# Define GPIOs for unique ID assignment
id_pins = [machine.Pin(2, machine.Pin.IN), machine.Pin(4, machine.Pin.IN), machine.Pin(16, machine.Pin.IN), machine.Pin(17, machine.Pin.IN)]

# Read GPIOs to determine device role
role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

# Read GPIO values and convert to integer ID
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# Display results
print("===================================")
print("ESP32 Role & ID Validation")
print("===================================")
print(f"Device Role: {DEVICE_TYPE}")
print(f"Device ID: {device_id}")
print("===================================")

# Continuous monitoring (optional)
while True:
    new_role_value = (role_pins[0].value() << 1) | role_pins[1].value()
    new_device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

    if new_role_value != role_value or new_device_id != device_id:
        role_value = new_role_value
        device_id = new_device_id
        DEVICE_TYPE = roles.get(role_value, "UNKNOWN")
        
        print("\n[UPDATE] GPIO Pins Changed:")
        print(f"New Role: {DEVICE_TYPE}")
        print(f"New ID: {device_id}")
    
    time.sleep(1)  # Check every second