import serial

# Open the serial port
ser = serial.Serial('/dev/serial0', 115200, timeout=1)  # Replace with your correct port (e.g., '/dev/ttyUSB0')

print("Listening for messages from Main ESP...")

try:
    while True:
        if ser.in_waiting > 0:
            # Read the incoming line and decode it
            line = ser.readline().decode('utf-8').strip()
            print(f"Received: {line}")
except KeyboardInterrupt:
    print("Exiting.")
    ser.close()
