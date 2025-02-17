import network
import espnow
import machine
import ubinascii
import time

# === Initialize WiFi in STA Mode (Required for ESP-NOW) ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# === Initialize ESP-NOW ===
esp = espnow.ESPNow()
esp.active(True)

# === Define GPIOs for role identification ===
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]
id_pins = [machine.Pin(2, machine.Pin.IN), machine.Pin(4, machine.Pin.IN), machine.Pin(16, machine.Pin.IN), machine.Pin(17, machine.Pin.IN)]

# === Read device role from GPIO ===
role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

# === Read unique device ID from GPIO ===
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# === Get Device MAC Address ===
esp_mac = ubinascii.hexlify(wlan.config('mac'), ':').decode()

print(f"[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}, MAC: {esp_mac}")

# === Peer Discovery (No Manual MAC Addresses) ===
known_peers = {}

def discover_peers():
    """Listen for peer announcements and store them."""
    while True:
        peer, msg = esp.recv()
        if msg:
            msg = msg.decode('utf-8')
            if msg.startswith("DISCOVER:"):
                peer_type, peer_id, peer_mac = msg.split(":")[1:]

                # Add sender or relay to known peers
                known_peers[peer_mac] = {"type": peer_type, "id": int(peer_id)}
                print(f"[DISCOVERED] {peer_type} {peer_id} at {peer_mac}")

                # Add as a peer in ESP-NOW
                esp.add_peer(peer_mac.encode())

        time.sleep(1)

# === Announce This Device (For Auto-Discovery) ===
def announce():
    """Broadcast our presence for peer discovery."""
    msg = f"DISCOVER:{DEVICE_TYPE}:{device_id}:{esp_mac}"
    esp.send(b'\xFF\xFF\xFF\xFF\xFF\xFF', msg.encode())  # Broadcast to all devices

# === Relay Logic (Dynamic Routing) ===
def relay_message():
    """Receive and forward messages dynamically."""
    while True:
        peer, msg = esp.recv()
        if msg:
            msg = msg.decode('utf-8')
            print(f"[RECEIVED] {msg} from {peer}")

            # Determine next-hop relay or receiver dynamically
            next_hop = None
            if DEVICE_TYPE == "RELAY":
                next_hop = next((mac for mac, data in known_peers.items() if data["type"] == "RECEIVER"), None)

            if next_hop:
                print(f"[FORWARDING] Sending to {next_hop}")
                esp.send(next_hop.encode(), msg.encode())
            else:
                print("[ERROR] No available next hop")

        time.sleep(0.1)

# === Start Execution Based on Role ===
announce()
discover_peers()

if DEVICE_TYPE == "RELAY":
    relay_message()
elif DEVICE_TYPE == "SENDER":
    print("[SENDER] Ready to send messages.")
elif DEVICE_TYPE == "RECEIVER":
    print("[RECEIVER] Ready to process incoming messages.")
