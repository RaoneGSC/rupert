import serial
import keyboard
import time

port = "COM4"  # adjust to your port
baudrate = 115200

ser = serial.Serial(port, baudrate, timeout=0)  # timeout=0 to avoid queue buildup

last_key = None        # stores last pressed key
press_interval = 0.2   # minimum seconds between repeated commands while key is held
last_command_time = 0  # stores time of last command sent

print("Control started! Use W, A, S, D to move. ESC to quit.")

while True:
    current_key = None
    current_time = time.time()

    if keyboard.is_pressed("w"):
        current_key = "w"
    elif keyboard.is_pressed("s"):
        current_key = "s"
    elif keyboard.is_pressed("a"):
        current_key = "a"
    elif keyboard.is_pressed("d"):
        current_key = "d"

    # send command only if key changed or held long enough
    if current_key and (current_key != last_key or current_time - last_command_time > press_interval):
        ser.write(current_key.encode() + b"\n")
        print(f"Sent: {current_key}")
        last_command_time = current_time

    last_key = current_key

    if keyboard.is_pressed("esc"):
        print("Exiting...")
        break

    time.sleep(0.05)

ser.close()
