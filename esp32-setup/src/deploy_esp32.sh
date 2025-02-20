#!/bin/bash

# Function to pause and prevent terminal from closing
pause() {
    read -p "Press any key to continue..."
}

# Function to detect COM port on Windows using PowerShell
detect_com_port() {
    echo "🔍 Checking available COM ports..."

    # Get list of COM ports using PowerShell
    AVAILABLE_PORTS=$(powershell -Command "Get-WmiObject Win32_SerialPort | Select-Object -ExpandProperty DeviceID")
    echo "ℹ️ Available Ports: $AVAILABLE_PORTS"

    # Check for COM6 or COM10
    for PORT in COM6 COM10; do
        if echo "$AVAILABLE_PORTS" | grep -q "$PORT"; then
            ESP_DEVICE=$PORT
            echo "✅ ESP32 detected at $ESP_DEVICE"
            break
        fi
    done

    # If neither COM6 nor COM10 is found
    if [ -z "$ESP_DEVICE" ]; then
        echo "❌ No ESP32 device found on COM6 or COM10. Please check the connection and try again."
        pause
        exit 1
    fi
}

# Check if we're on Windows
if [[ "$OS" == "Windows_NT" ]]; then
    echo "🔍 Detecting ESP32 device on Windows..."
    detect_com_port
else
    echo "🔍 Detecting ESP32 device on Linux..."

    # For Linux (e.g., Raspberry Pi)
    ESP_DEVICE=$(ls /dev/ttyUSB* 2>/dev/null)
    if [ -z "$ESP_DEVICE" ]; then
        echo "❌ No ESP32 device found. Please check the connection and try again."
        pause
        exit 1
    fi
    echo "✅ Found ESP32 at $ESP_DEVICE"
fi

echo "✅ Using ESP32 at $ESP_DEVICE"

# Prompt user for action
echo "Select an option:"
echo "1) Deploy ESP32 script (Sender/Relay/Receiver)"
echo "2) Erase flash and install new MicroPython firmware"
echo "3) Connect to ESP32 using minicom"
echo "4) View logs using mpremote repl"
echo "5) Run GPIO test script"
echo "6) View online devices (ESP32 only)"
echo "7) Monitor online devices from Raspberry Pi"
read -p "Enter choice (1/2/3/4/5/6/7): " OPTION

case $OPTION in
    1)
        # Deploy a specific ESP32 role
        echo "Select the ESP32 role:"
        echo "1) Sender"
        echo "2) Relay"
        echo "3) Receiver"
        read -p "Enter choice (1/2/3): " ROLE

        case $ROLE in
            1) FILE="espnow_sender.py"; ROLE_NAME="Sender";;
            2) FILE="espnow_relay.py"; ROLE_NAME="Relay";;
            3) FILE="espnow_receiver.py"; ROLE_NAME="Receiver";;
            *) echo "❌ Invalid choice. Exiting."; pause; exit 1;;
        esac

        echo "🚀 Deploying $FILE to ESP32 ($ROLE_NAME)..."

        # Step 1: Ensure MicroPython is installed
        echo "🔍 Checking if MicroPython is installed..."
        mpremote connect $ESP_DEVICE exec "print('MicroPython detected')" || {
            echo "❌ MicroPython not detected. Please flash MicroPython first."
            pause
            exit 1
        }

        # Step 2: Clean old files before flashing
        echo "🧹 Cleaning old files..."
        mpremote connect $ESP_DEVICE fs rm -r /main.py /online-devices.py 2>/dev/null

        # Step 3: Copy necessary files to ESP32
        echo "📂 Uploading required files..."
        mpremote connect $ESP_DEVICE fs cp $FILE :/main.py
        mpremote connect $ESP_DEVICE fs cp gpio_test.py :
        mpremote connect $ESP_DEVICE fs cp online-devices.py :

        # Step 4: Reset ESP32
        echo "🔄 Resetting ESP32..."
        mpremote connect $ESP_DEVICE reset

        echo "✅ Deployment complete! $FILE has been set as main.py"
        echo "📌 You can now monitor the ESP32 logs using: ./deploy_esp32.sh 4"
        ;;

    2)
        # Erase flash and install new MicroPython firmware
        read -p "⚠️ This will erase all data. Continue? (y/n): " CONFIRM
        if [ "$CONFIRM" != "y" ]; then
            echo "❌ Flashing canceled."
            pause
            exit 1
        fi

        read -p "Enter the path to the MicroPython .bin file: " BIN_FILE
        if [ ! -f "$BIN_FILE" ]; then
            echo "❌ File not found: $BIN_FILE"
            pause
            exit 1
        fi

        echo "🔥 Erasing ESP32 flash..."
        esptool.py --chip esp32 erase_flash

        echo "🚀 Writing new MicroPython firmware..."
        esptool.py --chip esp32 write_flash -z 0x1000 "$BIN_FILE"

        echo "✅ Flashing complete! Run './deploy_esp32.sh 1' to deploy scripts."
        ;;

    3)
        # Connect using minicom for debugging
        echo "🔌 Connecting to ESP32 using minicom..."
        echo "📌 To exit minicom, press CTRL + A, then X, then confirm with Y."
        sudo minicom -D $ESP_DEVICE -b 115200
        ;;

    4)
        # View logs using mpremote repl
        echo "📜 Viewing ESP32 logs (mpremote REPL)..."
        echo "📌 To exit, press CTRL + ]"
        mpremote connect $ESP_DEVICE repl
        ;;

    5)
        echo "🔧 Running GPIO test..."
        mpremote connect $ESP_DEVICE fs cp gpio_test.py :
        mpremote connect $ESP_DEVICE exec "import gpio_test"
        ;;

    6)
        echo "🔎 Viewing Online Devices (ESP32)..."
        mpremote connect $ESP_DEVICE fs cp online-devices.py :
        mpremote connect $ESP_DEVICE exec "import online-devices"
        ;;

    7)
        echo "🔎 Monitoring Online Devices from Raspberry Pi..."
        python3 online-devices.py
        ;;

    *)
        echo "❌ Invalid option. Exiting."
        pause
        exit 1
        ;;
esac

# === Prevent Terminal from Closing ===
echo "✅ Script execution completed."
pause
