import network
import espnow
import ubinascii
import time
import struct

# --- Activate Dual Mode: STA + AP ---
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=6)
ap = network.WLAN(network.AP_IF)
ap.active(True)
print("Dual mode active:")
print("  STA MAC:", ubinascii.hexlify(sta.config('mac')))
print("  AP  MAC:", ubinascii.hexlify(ap.config('mac')))

# --- Initialize ESP-NOW ---
esp = espnow.ESPNow()
esp.active(True)
print("ESP-NOW Initialized")

# --- Set Relay Virtual MAC and Device ID ---
# Relay virtual MAC uses the "AC:DB:01" prefix.
relay_virtual = "AC:DB:01:01:01"
device_id = 1  # This relay's ID (if needed for logging)
print("Relay Virtual MAC:", relay_virtual)

# --- Add the broadcast peer ---
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
try:
    esp.add_peer(broadcast_mac)
    print("Broadcast peer added on Relay")
except Exception as e:
    print("Warning: could not add broadcast peer:", e)

# --- Define the Relay Callback ---
def on_data_recv(*args):
    # Expect at least 2 args: peer and msg.
    if len(args) < 2:
        return
    peer, msg = args
    if not msg:
        return
    try:
        # Expecting data messages to be 22 bytes:
        #   Destination (16 bytes) | Sender ID (1 byte) | Msg Type (1 byte) | Ramp (2 bytes) | Motion (2 bytes)
        if len(msg) == 22:
            dest_field, sender_id, msg_type, ramp_state, motion_state = struct.unpack(">16sBBHH", msg)
            dest_virtual = dest_field.decode().strip('\x00')
            print("\nRelay received message:")
            print("  From Sender ID:", sender_id)
            print("  Destination Virtual MAC:", dest_virtual)
            print("  Msg Type:", msg_type, "Ramp:", ramp_state, "Motion:", motion_state)
            # If the message isn't addressed to this relay, forward it.
            if dest_virtual != relay_virtual:
                try:
                    # Forward the message using broadcast.
                    if esp.send(broadcast_mac, msg):
                        print("Relay forwarded message")
                    else:
                        print("Relay failed to forward message")
                except Exception as e:
                    print("Relay exception during forwarding:", e)
            else:
                print("Relay: Message is intended for me; processing locally if needed.")
        else:
            print("Relay: Received message with unexpected length:", len(msg))
    except Exception as e:
        print("Relay: Failed to process message:", e)

# --- Register the IRQ callback ---
esp.irq(on_data_recv)

print("Relay is ready, waiting for messages (polling fallback)...")
# --- Polling Loop as a Backup ---
while True:
    peer, msg = esp.recv()
    if msg:
        try:
            if len(msg) == 22:
                dest_field, sender_id, msg_type, ramp_state, motion_state = struct.unpack(">16sBBHH", msg)
                dest_virtual = dest_field.decode().strip('\x00')
                print("\nPoll: Received message:")
                print("  From Sender ID:", sender_id)
                print("  Destination Virtual MAC:", dest_virtual)
                print("  Msg Type:", msg_type, "Ramp:", ramp_state, "Motion:", motion_state)
                # Forward if not addressed to the relay itself.
                if dest_virtual != relay_virtual:
                    try:
                        if esp.send(broadcast_mac, msg):
                            print("Poll: Relay forwarded message")
                        else:
                            print("Poll: Relay failed to forward message")
                    except Exception as e:
                        print("Poll: Exception during forwarding:", e)
                else:
                    print("Poll: Message intended for this relay.")
            else:
                print("Poll: Received message with unexpected length:", len(msg))
        except Exception as e:
            print("Poll: Failed to process message:", e)
    time.sleep(1)
