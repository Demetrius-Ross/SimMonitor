import network
import espnow
import machine
import ubinascii
import time
import struct  # For unpacking data

# === Initialize WiFi in STA Mode (Required for ESP-NOW) ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# === Initialize ESP-NOW ===
esp = espnow.ESPNow()
esp.active(True)

# === Track Active Devices & Last Seen Timestamps ===
active_devices = {}  # {sender_id: last_seen_time}

# === Serial Setup for Forwarding Data to Raspberry Pi ===
uart = machine.UART(0, baudrate=115200, tx=1, rx=3)  # TX pin 1, RX pin 3

def on_data_recv(peer, msg):
    """Handle incoming ESP-NOW messages."""
    global active_devices

    if msg:
        sender_mac = ubinascii.hexlify(peer, ':').decode()
        data = struct.unpack(">BBHH", msg)  # Unpack received data

        sender_id = data[0]
        msg_type = data[1]  # 0xA1 = Data, 0xB1 = Heartbeat
        ramp_state = data[2]
        motion_state = data[3]

        # Update device last seen timestamp
        active_devices[sender_id] = time.time()

        if msg_type == 0xA1:  # Data Message
            msg_string = f"{sender_id},{ramp_state},{motion_state}"
            uart.write(msg_string + "\n")
            print(f"[RECEIVED DATA] {msg_string}")

        elif msg_type == 0xB1:  # Heartbeat Message
            print(f"[HEARTBEAT] Sender {sender_id} is online.")

# === Register ESP-NOW Receive Callback ===
esp.irq(on_data_recv)

print("[RECEIVER] Ready to process incoming messages.")

# === Monitor for Offline Devices ===
while True:
    current_time = time.time()
    for sender_id, last_seen in list(active_devices.items()):
        if current_time - last_seen > 60:
            print(f"[WARNING] Sender {sender_id} is OFFLINE (No heartbeat in 60s)")
            del active_devices[sender_id]

    time.sleep(5)  # Check every 5 seconds
