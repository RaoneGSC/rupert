import serial
import time

# Adjust to your Pico's serial port
SERIAL_PORT = 'COM4'  # change to your port
BAUDRATE = 115200

# Command to send (servo 1 angle, servo 2 angle)
command = "90,120\n"

try:
    with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=2) as ser:
        print(f"Connected to {SERIAL_PORT}")
        time.sleep(2)  # wait for Pico to initialize

        ser.write(command.encode())
        print(f"Command sent: {command.strip()}")

        while True:
            response = ser.readline().decode().strip()
            if response:
                print(f"Pico response: {response}")
            else:
                break

except serial.SerialException as e:
    print(f"Error opening serial port: {e}")
