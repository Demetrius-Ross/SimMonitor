import network
import espnow
import ubinascii
import machine
import time

# Initialize WiFi and ESP-NOW
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

esp = espnow.ESPNow()
esp.active(True)

# Define Receiver MAC Address (hardcoded for now)
receiver_mac = b'\xAC\xDB\x02\x00\x00\x00'  # Replace with actual receiver MAC

# Define GPIOs for role identification
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]

# Read role
role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

# Define GPIOs for unique ID assignment
id_pins = [machine.Pin(2, machine.Pin.IN), machine.Pin(4, machine.Pin.IN), machine.Pin(16, machine.Pin.IN), machine.Pin(17, machine.Pin.IN)]
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# Send heartbeat every 5 seconds
esp.add_peer(receiver_mac)

while True:
    msg = f"{DEVICE_TYPE}-{device_id} is online"
    print(f"Sending heartbeat: {msg}")
    esp.send(receiver_mac, msg)
    time.sleep(5)  # Send every 5 seconds
