import machine
import network
import espnow
import ubinascii

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

# Get base MAC address
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
mac = ubinascii.hexlify(wlan.config('mac'), ':').decode()

# Assign MAC Prefixes
mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02"}

# Construct device-specific MAC or unique identifier
unique_mac = f"{mac_prefix[DEVICE_TYPE]}:{device_id:02X}:{device_id:02X}"
print(f"Device Type: {DEVICE_TYPE}, ID: {device_id}, MAC: {unique_mac}")

# Initialize ESP-NOW
esp = espnow.ESPNow()
esp.active(True)

# Assign Peer Devices Dynamically
if DEVICE_TYPE == "SENDER":
    relay_mac = f"AC:DB:01:{device_id:02X}:{device_id:02X}"
    receiver_mac = f"AC:DB:02:00:00"
    esp.add_peer(relay_mac.encode())  # Add relay peer (if available)
    esp.add_peer(receiver_mac.encode())  # Add receiver as backup

elif DEVICE_TYPE == "RELAY":
    next_hop_mac = f"AC:DB:01:{(device_id+1):02X}:{(device_id+1):02X}"  # Example: Forward to next relay
    receiver_mac = f"AC:DB:02:00:00"
    esp.add_peer(next_hop_mac.encode())
    esp.add_peer(receiver_mac.encode())

elif DEVICE_TYPE == "RECEIVER":
    print("Receiver is waiting for messages...")

# Send Test Message (For Debugging)
esp.send(receiver_mac.encode(), f"Hello from {DEVICE_TYPE} {device_id}")