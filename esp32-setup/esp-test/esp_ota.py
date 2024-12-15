import serial
import time
import os

# Configure the serial connection to the main ESP32
SERIAL_PORT = "/dev/ttyUSB0"  # Update this with your serial port (e.g., COM3 for Windows)
BAUD_RATE = 115200
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

# Path to the firmware binary
FIRMWARE_PATH = "firmware.bin"

def send_ota_command(target_label):
    """
    Send the OTA start command to the main ESP32.
    :param target_label: The label of the target Node ESP32 (e.g., "PC-12").
    """
    ota_command = f"OTA:{target_label}\n"
    ser.write(ota_command.encode())
    print(f"Sent OTA command for target: {target_label}")

def send_firmware():
    """
    Send the firmware binary file in chunks over serial.
    """
    if not os.path.exists(FIRMWARE_PATH):
        print(f"Error: Firmware file '{FIRMWARE_PATH}' does not exist.")
        return

    # Read and send the firmware file in 1 KB chunks
    with open(FIRMWARE_PATH, "rb") as firmware:
        chunk = firmware.read(1024)  # 1 KB chunk
        while chunk:
            ser.write(chunk)  # Send the chunk over serial
            time.sleep(0.1)  # Adjust delay if needed for reliable transfer
            chunk = firmware.read(1024)
    print("Firmware transfer complete!")

def main():
    # Specify the target Node ESP32 label
    target_label = "PC-12"  # Change to your desired Node ESP32 label (e.g., "EC-130")

    # Send the OTA start command
    send_ota_command(target_label)

    # Wait for the main ESP32 to enter OTA mode
    print("Waiting for the ESP32 to enter OTA mode...")
    time.sleep(2)  # Adjust delay based on your setup

    # Send the firmware file
    print("Sending firmware...")
    send_firmware()

if __name__ == "__main__":
    main()
