#!/bin/bash

# Deployment Script for ESP32 with MicroPython

echo "🔍 Detecting ESP32 device..."
ESP_DEVICE=$(ls /dev/ttyUSB* 2>/dev/null)

if [ -z "$ESP_DEVICE" ]; then
    echo "❌ No ESP32 device found. Please check the connection and try again."
    exit 1
fi

echo "✅ Found ESP32 at $ESP_DEVICE"

# Prompt user for the ESP32 role
echo "Select the ESP32 role:"
echo "1) Sender"
echo "2) Relay"
echo "3) Receiver"
read -p "Enter choice (1/2/3): " ROLE

# Determine the file to flash
case $ROLE in
    1) FILE="espnow_sender.py";;
    2) FILE="espnow_relay.py";;
    3) FILE="espnow_receiver.py";;
    *) echo "❌ Invalid choice. Exiting."; exit 1;;
esac

echo "🚀 Deploying $FILE to ESP32..."

# Flash the selected role file as main.py
mpremote connect $ESP_DEVICE fs cp boot.py :
mpremote connect $ESP_DEVICE fs cp $FILE :/main.py

# Reset ESP32
mpremote connect $ESP_DEVICE reset

echo "✅ Deployment complete! $FILE has been set as main.py"


# Permissions: chmod +x deploy_esp32.sh
# Run Script: ./deploy_esp32.sh
