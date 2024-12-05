import serial
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout = 1)
print(f"Serial port open: {ser.is_open}")

while True:
    if ser.in_waiting > 0:
        data = ser.readline().decode('utf-8', errors='ignore').strip()
        print(f"Data recieved {data}")
    else:
            #print("No data available")
            pass