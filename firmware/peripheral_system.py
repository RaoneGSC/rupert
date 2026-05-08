# pico_servo_protected.py
# Runs on Raspberry Pi Pico 2 (MicroPython)
# Receives 5 comma-separated angles via USB serial and drives the servos.
import sys
from machine import Pin, PWM
import time

# --- PWM objects ---
servo_pins = [15, 14, 13, 12, 19]
servos = [PWM(Pin(p)) for p in servo_pins]
for s in servos:
    s.freq(50)

# --- Duty cycle calibration ---
DUTY_MIN_SG92R_MG90S = 2000
DUTY_MAX_SG92R_MG90S = 8000
DUTY_MIN_SG90 = 1638
DUTY_MAX_SG90 = 8192

# --- Servo types per joint ---
servo_kind = ["SG92R", "MG90S", "SG92R", "SG90", "SG90"]

# --- Safety angle limits ---
ANGLE_MIN = [0,   0,   0,   0,   0]
ANGLE_MAX = [180, 180, 180, 180, 180]

# --- Initial state ---
current_angles = [90, 90, 90, 90, 90]

def angle_to_duty(angle, kind):
    angle = max(0, min(180, int(angle)))
    if kind in ("SG92R", "MG90S"):
        return int((angle / 180) * (DUTY_MAX_SG92R_MG90S - DUTY_MIN_SG92R_MG90S) + DUTY_MIN_SG92R_MG90S)
    else:
        return int((angle / 180) * (DUTY_MAX_SG90 - DUTY_MIN_SG90) + DUTY_MIN_SG90)

# Move all servos to initial position
for i in range(5):
    servos[i].duty_u16(angle_to_duty(current_angles[i], servo_kind[i]))
time.sleep(0.2)
print("READY")

# Main loop — waits for commands on stdin (USB serial)
while True:
    try:
        line = sys.stdin.readline()
        if not line:
            continue
        cmd = line.strip()
        if not cmd:
            continue
        parts = cmd.split(",")
        if len(parts) != 5:
            print("ERR,FORMAT")
            continue
        targets = [max(ANGLE_MIN[i], min(ANGLE_MAX[i], int(float(p)))) for i, p in enumerate(parts)]
        for i in range(5):
            current_angles[i] = targets[i]
            servos[i].duty_u16(angle_to_duty(current_angles[i], servo_kind[i]))
        print("OK," + ",".join(str(a) for a in current_angles))
    except Exception as e:
        print("ERR," + str(e))
