import time
import sys
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/pts/6"
BAUD = 115200

ser = serial.Serial(PORT, BAUD)

def send(sim_id, ramp, motion):
    msg = f"[DATA] Received from Sender ID {sim_id}: RampState={ramp}, MotionState={motion}, Seq=1\n"
    ser.write(msg.encode())
    ser.flush()
    print("Sent:", msg.strip())


# Demo motion sequence
while True:
    send(1, 1, 2)  # sim 1 in motion, ramp up
    send(2, 1, 2)  # sim 2 in motion, ramp up
    send(3, 1, 2)  # sim 3 in motion, ramp up
    time.sleep(2)

    send(1, 2, 1)  # standby
    time.sleep(2)

    send(1, 0, 1)  # ramp moving
    time.sleep(2)

    send(1, 1, 1)  # ramp up
    send(2, 1, 1)  # sim 2 ramp up
    time.sleep(2)
