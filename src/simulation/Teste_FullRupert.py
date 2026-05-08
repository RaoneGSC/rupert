# pc_control_protected.py
import serial, time, sys
from pynput import keyboard

PORTA = "COM4"
BAUD = 230400
ser = serial.Serial(PORTA, BAUD, timeout=0.2)
# --- Estado ---
angles = [90.0]*5
last_sent = angles.copy()
# --- Parâmetros ---
STEP_BASE = [5.0, 2.0, 5.0, 5.0, 5.0]   # passo por tick (°) - eixo 2 reduzido
STEP_MAX  = [10.0, 4.0, 10.0, 10.0, 10.0] # passo máximo
ACCEL     = [2.0, 0.5, 2.0, 2.0, 2.0]   # aceleração
DELAY     = 0.05                         # 20Hz
DEADBAND  = 1.0
ANGLE_MIN = [5, 5, 5, 0, 0]
ANGLE_MAX = [175, 160, 175, 180, 180]  # eixo 2 limitado

# --- Controle por tecla ---
key_state = {k: False for k in ['w','s','a','d','q','e','z','x','c','v']}
servo_step = [0.0]*5

key_map = {
    "w": (0, +1), "s": (0, -1),
    "a": (1, -1), "d": (1, +1),
    "q": (2, +1), "e": (2, -1),
    "z": (3, +1), "x": (3, -1),
    "c": (4, +1), "v": (4, -1),
}

def enviar():
    cmd = ",".join(str(int(round(a))) for a in angles) + "\n"
    ser.write(cmd.encode())
    try:
        resp = ser.readline().decode().strip()
        if resp:
            print("Pico:", resp)
    except:
        pass

def on_press(key):
    try:
        k = key.char
    except AttributeError:
        return
    if k in key_map:
        key_state[k] = True

def on_release(key):
    try:
        k = key.char
    except AttributeError:
        return
    if k in key_map:
        key_state[k] = False

from pynput import keyboard
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

# envia posição inicial
enviar()
time.sleep(0.1)

try:
    while True:
        changed = False
        for i in range(5):
            step = 0.0
            for k, pressed in key_state.items():
                if pressed and k in key_map:
                    idx, sign = key_map[k]
                    if idx == i:
                        # aceleração progressiva
                        servo_step[i] = min(STEP_MAX[i], servo_step[i] + ACCEL[i])
                        step += servo_step[i] * sign
            # desacelera suavemente
            if step == 0.0:
                servo_step[i] = max(0.0, servo_step[i] - ACCEL[i])

            if step != 0.0:
                angles[i] += step * (DELAY/0.05)
                angles[i] = max(ANGLE_MIN[i], min(ANGLE_MAX[i], angles[i]))

            if abs(angles[i]-last_sent[i]) >= DEADBAND:
                changed = True

        if changed:
            enviar()
            last_sent = angles.copy()

        time.sleep(DELAY)

except KeyboardInterrupt:
    print("Encerrando...")
    ser.close()
    sys.exit()
