import serial

# Open the serial port
ser = serial.Serial('/dev/serial0', 115200, timeout=1)
ser.flush()

while True:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8').rstrip()
        print(f"Received from ESP: {line}")
