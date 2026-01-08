# gpio_test_mkiv_legacy_led_macsim.py
# ------------------------------------------------------------
# GPIO Role & ID Verification (MKIV + Legacy aware)
#
# What it does:
#   Detects MKIV mode:
#        MKIV if ONLY GPIO19 is HIGH (GPIO18=0, GPIO14=0)
#   Decodes role correctly for MKIV vs Legacy
#   Decodes device_id with the correct hex switch logic:
#        MKIV:   raw_id=(17<<3)|(5<<2)|(4<<1)|16 ; device_id = raw_id ^ 0x0F
#        Legacy: device_id=(4<<0)|(16<<1)|(17<<2)|(5<<3) ; (no XOR)
#   Shows Virtual MAC + Real ESP32 MAC
#   MKIV only: drives a WS2812/NeoPixel LED on GPIO27 to show role + blink patterns
#   "Simulate broadcast of true MAC":
#        - Prints an "IDENTITY" line that mimics what your ESP-NOW identity packet represents
#        - Optionally prints it repeatedly every N seconds (no ESP-NOW needed)
#
# Notes:
#   • Legacy boards have NO LED support (code won't try unless MKIV flag is true).
#   • If your board's WS2812 isn't a NeoPixel / requires different timing, tell me.
# ------------------------------------------------------------

import machine
import ubinascii
import network
import time

# NeoPixel is common on ESP32 MicroPython builds; guarded import
try:
    import neopixel
except Exception:
    neopixel = None


# =========================================================
# Role pins + MKIV detect
# =========================================================
PIN19 = machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_DOWN)  # "unused role pin" / MKIV flag
PIN18 = machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_DOWN)
PIN14 = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN)

time.sleep_ms(50)

mkiv_flag = (PIN19.value() == 1 and PIN18.value() == 0 and PIN14.value() == 0)

roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER", 3: "TELEMETRY"}

if mkiv_flag:
    # MKIV uses GPIO18/GPIO14 as a 2-bit role selector
    role_value = (PIN18.value() << 1) | PIN14.value()
else:
    # Legacy uses GPIO18/GPIO19 as a 2-bit role selector (espnow-combined behavior)
    role_value = (PIN18.value() << 1) | PIN19.value()

DEVICE_TYPE = roles.get(role_value, "UNKNOWN")


# =========================================================
# Hex switch decode (MKIV vs Legacy)
# =========================================================
if mkiv_flag:
    # MKIV current logic:
    # A=17(bit3), B=5(bit2), C=4(bit1), D=16(bit0), then invert
    A = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
    B = machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    C = machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    D = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)

    raw_id = (A.value() << 3) | (B.value() << 2) | (C.value() << 1) | D.value()
    device_id = raw_id ^ 0x0F
    id_logic = "MKIV: raw=(17<<3)|(5<<2)|(4<<1)|16 ; id=raw^0x0F"
else:
    # Legacy logic (espnow-combined):
    # device_id = (GPIO4<<0)|(GPIO16<<1)|(GPIO17<<2)|(GPIO5<<3)
    P4  = machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    P16 = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)
    P17 = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
    P5  = machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN)

    raw_id = (P4.value() << 0) | (P16.value() << 1) | (P17.value() << 2) | (P5.value() << 3)
    device_id = raw_id
    id_logic = "LEGACY: id=(4<<0)|(16<<1)|(17<<2)|(5<<3) ; (no XOR)"


# =========================================================
# MACs
# =========================================================
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
real_mac = ubinascii.hexlify(wlan.config("mac"), ":").decode()

mac_prefix = {
    "SENDER":   "AC:DB:00",
    "RELAY":    "AC:DB:01",
    "RECEIVER": "AC:DB:02",
    "TELEMETRY":"AC:DB:03",
}
virtual_mac = "{}:{:02X}:{:02X}".format(mac_prefix.get(DEVICE_TYPE, "AC:DB:FF"), device_id, device_id)


# =========================================================
# MKIV LED support (GPIO27 WS2812/NeoPixel)
# =========================================================
LED_PIN = 27
np = None
if mkiv_flag and neopixel is not None:
    try:
        np = neopixel.NeoPixel(machine.Pin(LED_PIN, machine.Pin.OUT), 1)
    except Exception:
        np = None

def led_set(r, g, b):
    if np is None:
        return
    np[0] = (r, g, b)
    np.write()

def led_blink(r, g, b, times=2, on_ms=120, off_ms=120):
    if np is None:
        return
    for _ in range(times):
        led_set(r, g, b)
        time.sleep_ms(on_ms)
        led_set(0, 0, 0)
        time.sleep_ms(off_ms)

def role_color(role: str):
    if role == "SENDER":
        return (0, 25, 0)
    if role == "RELAY":
        return (0, 0, 25)
    if role == "RECEIVER":
        return (25, 0, 25)
    if role == "TELEMETRY":
        return (25, 15, 0)
    return (10, 10, 10)


# =========================================================
# Output
# =========================================================
print("\n=== GPIO ROLE & ID VERIFICATION (MKIV + LEGACY) ===")
print("MKIV Flag             :", mkiv_flag)
print("Role Pins (19,18,14)   : {} {} {}".format(PIN19.value(), PIN18.value(), PIN14.value()))
print("Role Value             :", role_value)
print("Device Role            :", DEVICE_TYPE)
print("ID Logic               :", id_logic)
print("Raw ID                 : 0x{:X} ({})".format(raw_id, raw_id))
print("Device ID              : {} (0x{:02X})".format(device_id, device_id))
print("Generated Virtual MAC  :", virtual_mac)
print("Actual ESP32 MAC       :", real_mac)
print("===================================================\n")

ok = True
if DEVICE_TYPE == "UNKNOWN":
    print("[ERROR] Invalid role configuration.")
    ok = False
if device_id < 0 or device_id > 15:
    print("[ERROR] Invalid device ID (must be 0..15).")
    ok = False

if ok:
    print("[OK] GPIO configuration is valid.")

# LED behavior:
# - MKIV only
# - Steady role color
# - Blink white once if OK, blink red 3x if error
if mkiv_flag and np is not None:
    led_set(*role_color(DEVICE_TYPE))
    time.sleep_ms(80)
    if ok:
        led_blink(25, 25, 25, times=1, on_ms=120, off_ms=80)
    else:
        led_blink(25, 0, 0, times=3, on_ms=120, off_ms=120)


# =========================================================
# "Simulate broadcast of true MAC addresses"
# =========================================================
# In ESP-NOW, identity broadcast is essentially (virtual_mac, real_mac).
# Here we simply PRINT a line that represents that broadcast, and can repeat it.
#
# Toggle these as needed:
SIMULATE_IDENTITY_BROADCAST = True
BROADCAST_EVERY_SEC = 5   # set to 0 to only print once

if SIMULATE_IDENTITY_BROADCAST:
    # One-time "broadcast"
    print("[IDENTITY_SIM] {} => {}".format(virtual_mac, real_mac))

    # Optional repeating simulation
    if BROADCAST_EVERY_SEC and BROADCAST_EVERY_SEC > 0:
        print("[IDENTITY_SIM] Repeating every {}s (Ctrl+C to stop)".format(BROADCAST_EVERY_SEC))
        try:
            while True:
                time.sleep(BROADCAST_EVERY_SEC)
                print("[IDENTITY_SIM] {} => {}".format(virtual_mac, real_mac))
                # quick LED pulse cyan to indicate "identity broadcast"
                if mkiv_flag and np is not None:
                    led_blink(0, 25, 25, times=1, on_ms=60, off_ms=30)
                    led_set(*role_color(DEVICE_TYPE))
        except KeyboardInterrupt:
            if mkiv_flag and np is not None:
                led_set(0, 0, 0)
            print("\n[IDENTITY_SIM] Stopped.")