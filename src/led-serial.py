import serial

# Open the serial port
ser = serial.Serial('/dev/serial0', 115200, timeout=1)

print("Listening for LED statuses...")

try:
    while True:
        if ser.in_waiting > 0:
            # Read and print the incoming line
            line = ser.readline().decode('utf-8').strip()
            print(f"Received: {line}")
except KeyboardInterrupt:
    print("Exiting...")
    ser.close()
