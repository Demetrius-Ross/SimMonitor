import network

# Initialize WiFi in STA mode (Required for ESP-NOW)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
