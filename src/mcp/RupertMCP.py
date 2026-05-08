#!/usr/bin/env python3
# RupertMCP.py — MCP server for controlling Rupert via Claude Desktop
import serial, time, sys
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP

# ─── Serial ───────────────────────────────────────────────────────────────────
PORT = "COM4"
BAUD  = 230400
ser   = serial.Serial(PORT, BAUD, timeout=0.2)

# ─── State ────────────────────────────────────────────────────────────────────
angles = [90.0] * 5

# ─── Parameters ───────────────────────────────────────────────────────────────
STEP_BASE = [5.0,  2.0,  5.0,  5.0,  5.0]
DELAY     = 0.05
DEADBAND  = 1.0
ANGLE_MIN = [5,   5,   5,   0,   0]
ANGLE_MAX = [175, 160, 175, 180, 180]
SERVOS    = ["base", "shoulder", "elbow", "wrist", "gripper"]
GRIP_IDX         = 4    # gripper servo index
GRIP_HOLD_OFFSET = 10   # extra degrees to maintain grip pressure

# ─── Serial communication ──────────────────────────────────────────────────────
def send():
    cmd_angles = angles.copy()
    g = cmd_angles[GRIP_IDX]
    if abs(g - 90) > 5:  # outside neutral = gripping something
        direction = 1 if g > 90 else -1
        cmd_angles[GRIP_IDX] = max(ANGLE_MIN[GRIP_IDX], min(ANGLE_MAX[GRIP_IDX], g + direction * GRIP_HOLD_OFFSET))
    cmd = ",".join(str(int(round(a))) for a in cmd_angles) + "\n"
    ser.write(cmd.encode())
    try:
        resp = ser.readline().decode().strip()
        if resp:
            print(f"[Pico] {resp}", flush=True, file=sys.stderr)
    except Exception:
        pass

def move_to(idx: int, target: float):
    target = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], target))
    dist = abs(target - angles[idx])
    if dist <= DEADBAND:
        return
    angles[idx] = target
    send()
    # wait proportional to distance so servo has time to reach target
    time.sleep(max(0.4, dist * 0.025))

# ─── MCP Server ───────────────────────────────────────────────────────────────
mcp = FastMCP("Rupert")

@mcp.tool()
def move_servo(servo: str, angle: float) -> str:
    """Move a robot servo to the specified angle.

    Servos and correct directions:
      - base      : RIGHT=smaller angle (e.g. 45°)    LEFT=larger angle (e.g. 135°)   forward=90°
      - shoulder  : UP=larger angle (e.g. 130°)       DOWN=smaller angle (e.g. 45°)   horizontal=90°
      - elbow     : EXTEND=larger angle (e.g. 135°)   FOLD=smaller angle (e.g. 45°)   straight=90°
      - wrist     : OPEN gripper=0°                   CLOSE gripper=180°
      - gripper   : wrist/gripper rotation             neutral=90°

    Args:
        servo: servo name (base, shoulder, elbow, wrist or gripper)
        angle: target angle in degrees
    """
    servo = servo.lower().strip()
    if servo not in SERVOS:
        return f"Invalid servo '{servo}'. Use: {', '.join(SERVOS)}"
    idx  = SERVOS.index(servo)
    target = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], float(angle)))
    print(f"→ {servo} → {target:.0f}°", flush=True, file=sys.stderr)
    move_to(idx, target)
    return f"{servo} positioned at {angles[idx]:.0f}°"

@mcp.tool()
def current_position() -> str:
    """Returns the current position in degrees of all robot servos."""
    parts = [f"{SERVOS[i]}: {angles[i]:.0f}°" for i in range(5)]
    return "Current position → " + " | ".join(parts)

@mcp.tool()
def center_all() -> str:
    """Moves all servos to 90° (robot center/neutral position)."""
    print("→ Centering...", flush=True, file=sys.stderr)
    for i in range(5):
        move_to(i, 90.0)
    return "Robot centered at 90° on all axes."

@mcp.tool()
def move_sequence(movements: List[Dict[str, Any]]) -> str:
    """Executes a sequence of movements on multiple servos.

    Use for commands involving more than one servo at a time.

    Args:
        movements: list of objects {"servo": str, "angle": float}
                   Example: [{"servo": "shoulder", "angle": 130}, {"servo": "wrist", "angle": 0}]
    """
    results = []
    for m in movements:
        s = str(m.get("servo", "")).lower().strip()
        a = m.get("angle")
        if s in SERVOS and a is not None:
            idx    = SERVOS.index(s)
            target = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], float(a)))
            print(f"→ {s} → {target:.0f}°", flush=True, file=sys.stderr)
            move_to(idx, target)
            results.append(f"{s}={angles[idx]:.0f}°")
        else:
            results.append(f"skipped: {m}")
    return "Sequence done: " + ", ".join(results)

# ─── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Rupert MCP Server starting...", flush=True, file=sys.stderr)
    send()
    time.sleep(0.1)
    print("Ready. Waiting for Claude Desktop.", flush=True, file=sys.stderr)
    mcp.run()
