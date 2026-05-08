from isaacsim.core.prims import SingleArticulation
import asyncio
import serial
import numpy as np
import threading
import time

# ---------------- CONFIG ----------------
ART_PATH = "/World/Rupert"
COM_PORT = "COM4"
BAUD = 230400
RAD_TO_DEG = 180.0 / np.pi
PRINT_LOOP_SLEEP = 0.5   # seconds between debug prints
ANGLE_THRESHOLD_DEG = [0.15, 3.0, 3.0, 0.15, 0.15]  # elbow needs more torque than shoulder
MIN_SEND_INTERVAL = 0.02  # minimum interval between serial sends
GRIP_IDX         = 4    # gripper servo index
GRIP_HOLD_OFFSET = 10   # extra degrees to maintain grip pressure
LOOP_SLEEP = 0.005        # main loop stability sleep
# ----------------------------------------

art = SingleArticulation(prim_path=ART_PATH)

# thread-safe serial sender
_latest_cmd = None
_latest_lock = threading.Lock()
_cmd_event = threading.Event()
_thread_stop = threading.Event()

def _set_latest_cmd(cmd_bytes: bytes):
    with _latest_lock:
        global _latest_cmd
        _latest_cmd = cmd_bytes
    if not _cmd_event.is_set():
        _cmd_event.set()

def _serial_sender_loop():
    while not _thread_stop.is_set():
        try:
            if not _cmd_event.wait(timeout=0.01):
                continue
            with _latest_lock:
                cmd = _latest_cmd
            _cmd_event.clear()
            if cmd and ser and ser.is_open:
                # drain OK/ERR responses from Pico before writing
                if ser.in_waiting > 0:
                    ser.reset_input_buffer()
                ser.write(cmd)
        except Exception as e:
            print("Serial sender error:", e)

if not globals().get("_SERIAL_SENDER_THREAD_STARTED"):
    sender_thread = threading.Thread(target=_serial_sender_loop, daemon=True)
    sender_thread.start()
    globals()["_SERIAL_SENDER_THREAD_STARTED"] = True
    globals()["_SERIAL_SENDER_THREAD"] = sender_thread

try:
    ser = serial.Serial(COM_PORT, BAUD, timeout=0.1)
    ser.reset_input_buffer()   # clear buffer on open
except Exception as e:
    ser = None
    print("Serial open failed:", e)

# joint limits and mappings
JOINT_LIMITS = [
    (-130, -60),   # J0 Base
    (-60, 100),    # J1 Shoulder
    (-250, -20),   # J2 Arm
    (-30, 60),     # J3 Hand
    (-90, 90),     # J4 Forearm
]

# per-joint sign correction
JOINT_SIGN = [1, 1, 1, 1, -1]
JOINT_OFFSET = [0, 20, -10, 0, -10]  # degrees

# mapping between simulation indices and physical robot indices
IDX_MAP = [6, 2, 0, 4, 1]  # adjust to match your robot

def sim_to_servo(joint_idx: int, sim_angle_deg: float) -> int:
    jmin, jmax = JOINT_LIMITS[joint_idx]
    angle = sim_angle_deg * JOINT_SIGN[joint_idx] + JOINT_OFFSET[joint_idx]
    servo = (angle - jmin) * (180.0 / (jmax - jmin))
    return max(0, min(180, int(servo)))

# optional debug task
async def print_joint_angles():
    while True:
        try:
            if art.is_valid():
                joint_positions = art.get_joint_positions()
                if joint_positions is not None:
                    print("===== Joint Debug =====")
                    for i, jp in enumerate(joint_positions):
                        print(f"Index {i}: {float(jp)*RAD_TO_DEG:.2f}°")
                    print("-----------------------")
        except Exception as e:
            print("Error reading joints:", e)

        await asyncio.sleep(PRINT_LOOP_SLEEP)

loop = asyncio.get_event_loop()
_existing_debug = [t for t in asyncio.all_tasks(loop) if t.get_coro().__name__ == "print_joint_angles"]
if not _existing_debug:
    loop.create_task(print_joint_angles())

# main loop state
_last_angles  = [None] * 5
_last_send_time = 0.0
_RAMP_STEPS   = 20          # 20 × MIN_SEND_INTERVAL ≈ 400 ms
_ramp_count   = 0
_ramp_origin  = [90.0] * 5
_ramp_target  = None        # set on first valid frame

def _sim_to_servos(angles_deg):
    result = []
    for i, idx in enumerate(IDX_MAP):
        s = sim_to_servo(i, angles_deg[idx])
        if i == GRIP_IDX and abs(s - 90) > 5:
            d = 1 if s > 90 else -1
            s = max(0, min(180, s + d * GRIP_HOLD_OFFSET))
        result.append(s)
    return result

async def read_and_send_angles():
    global _last_angles, _last_send_time, _ramp_count, _ramp_target
    while True:
        try:
            if art.is_valid():
                joint_positions = art.get_joint_positions()
                if joint_positions is not None and len(joint_positions) > max(IDX_MAP):
                    angles_deg = [float(jp) * RAD_TO_DEG for jp in joint_positions]
                    now = time.time()

                    if (now - _last_send_time) < MIN_SEND_INTERVAL:
                        await asyncio.sleep(LOOP_SLEEP)
                        continue

                    # startup ramp: smoothly interpolate from 90° to sim position
                    if _ramp_count < _RAMP_STEPS:
                        if _ramp_target is None:
                            _ramp_target = _sim_to_servos(angles_deg)
                        t = (_ramp_count + 1) / _RAMP_STEPS
                        servos = [int(_ramp_origin[i] + t * (_ramp_target[i] - _ramp_origin[i])) for i in range(5)]
                        _ramp_count += 1
                        if _ramp_count >= _RAMP_STEPS:
                            _last_angles = [angles_deg[idx] for idx in IDX_MAP]

                    # normal operation
                    else:
                        changed = any(
                            _last_angles[i] is None or
                            abs(angles_deg[idx] - _last_angles[i]) >= ANGLE_THRESHOLD_DEG[i]
                            for i, idx in enumerate(IDX_MAP)
                        )
                        if not changed:
                            await asyncio.sleep(LOOP_SLEEP)
                            continue
                        servos = _sim_to_servos(angles_deg)
                        _last_angles = [angles_deg[idx] for idx in IDX_MAP]

                    cmd = ",".join(str(s) for s in servos) + "\r\n"
                    _set_latest_cmd(cmd.encode("ascii"))
                    _last_send_time = now

        except Exception as e:
            print("Error reading joints:", e)

        await asyncio.sleep(LOOP_SLEEP)

_existing = [t for t in asyncio.all_tasks(loop) if t.get_coro().__name__ == "read_and_send_angles"]
if not _existing:
    loop.create_task(read_and_send_angles())
