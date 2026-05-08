#!/usr/bin/env python3
# RupertPhysicalAI.py — Natural language control with LangChain + Groq
import os, serial, time, sys, threading
from typing import List, Dict, Any
from langchain_groq import ChatGroq
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

# ─── API Key ──────────────────────────────────────────────────────────────────
if not os.environ.get("GROQ_API_KEY"):
    raise EnvironmentError("GROQ_API_KEY is not set. Create a .env file with the variable.")

# ─── Spinner control ──────────────────────────────────────────────────────────
_stop_spin = threading.Event()
_stop_spin.set()  # starts stopped

# ─── Serial ───────────────────────────────────────────────────────────────────
PORT = "COM4"
BAUD  = 230400
ser   = serial.Serial(PORT, BAUD, timeout=0.2)

# ─── State ────────────────────────────────────────────────────────────────────
angles    = [90.0] * 5
last_sent = angles.copy()

# ─── Parameters ───────────────────────────────────────────────────────────────
STEP_BASE = [5.0,  2.0,  5.0,  5.0,  5.0]
STEP_MAX  = [10.0, 4.0, 10.0, 10.0, 10.0]
ACCEL     = [2.0,  0.5,  2.0,  2.0,  2.0]
DELAY     = 0.05
DEADBAND  = 1.0
ANGLE_MIN = [5,   5,   5,   0,   0]
ANGLE_MAX = [175, 160, 175, 180, 180]

SERVOS = ["base", "shoulder", "elbow", "wrist", "gripper"]

# ─── Serial communication ──────────────────────────────────────────────────────
def send():
    cmd = ",".join(str(int(round(a))) for a in angles) + "\n"
    ser.write(cmd.encode())
    try:
        resp = ser.readline().decode().strip()
        if resp:
            print(f"  [Pico] {resp}")
    except Exception:
        pass

def move_to(idx: int, target: float):
    """Smooth interpolation to target angle using STEP_BASE."""
    target = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], target))
    step = STEP_BASE[idx]
    while abs(angles[idx] - target) > DEADBAND:
        diff = target - angles[idx]
        move = min(step, abs(diff)) * (1 if diff > 0 else -1)
        angles[idx] = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], angles[idx] + move))
        send()
        time.sleep(DELAY)

# ─── LangChain tools ──────────────────────────────────────────────────────────
@tool
def move_servo(servo: str, angle: str) -> str:
    """Move a robot servo to the specified angle.

    Available servos and limits:
      - base     : 5–175°  | RIGHT=smaller angle (e.g. 45°)   LEFT=larger angle (e.g. 135°)   forward=90°
      - shoulder : 5–160°  | UP=larger angle (e.g. 130°)      DOWN=smaller angle (e.g. 45°)    horizontal=90°
      - elbow    : 5–175°  | EXTEND=larger angle (e.g. 135°)  FOLD=smaller angle (e.g. 45°)    straight=90°
      - wrist    : 0–180°  | OPEN gripper=smaller angle (0°)  CLOSE gripper=larger angle (180°)
      - gripper  : 0–180°  | wrist/gripper rotation            neutral=90°

    Args:
        servo: servo name (base, shoulder, elbow, wrist or gripper)
        angle: target angle in degrees
    """
    servo = servo.lower().strip()
    if servo not in SERVOS:
        return f"Invalid servo '{servo}'. Choose: {', '.join(SERVOS)}"
    idx    = SERVOS.index(servo)
    target = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], float(angle)))
    print(f"  → {servo} → {target:.0f}°")
    move_to(idx, target)
    return f"{servo} positioned at {angles[idx]:.0f}°"

@tool
def current_position() -> str:
    """Returns the current position (in degrees) of all robot servos."""
    parts = [f"{SERVOS[i]}: {angles[i]:.0f}°" for i in range(5)]
    return "Current position → " + " | ".join(parts)

@tool
def center_all() -> str:
    """Moves all servos to 90° (robot center/neutral position)."""
    print("  → Centering all servos...")
    for i in range(5):
        move_to(i, 90.0)
    return "Robot centered at 90° on all axes."

@tool
def move_sequence(movements: List[Dict[str, Any]]) -> str:
    """Executes a sequence of movements on multiple servos.

    Use this tool for compound commands involving more than one servo.

    Args:
        movements: list of objects {"servo": str, "angle": float}
                   Example: [{"servo": "base", "angle": 120}, {"servo": "gripper", "angle": 0}]
    """
    results = []
    for m in movements:
        s = str(m.get("servo", "")).lower().strip()
        a = m.get("angle")
        if s in SERVOS and a is not None:
            idx    = SERVOS.index(s)
            target = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], float(a)))
            print(f"  → {s} → {target:.0f}°")
            move_to(idx, target)
            results.append(f"{s}={angles[idx]:.0f}°")
        else:
            results.append(f"skipped: {m}")
    return "Sequence done: " + ", ".join(results)

@tool
def ask_clarification(question: str) -> str:
    """Use this tool when a command is ambiguous or you don't know how to execute it.
    Displays the question to the user and waits for a response.

    Args:
        question: the clarification question for the user
    """
    _stop_spin.set()
    print(f"\n  Rupert: {question}")
    answer = input("  You: ").strip()
    return f"User replied: {answer}"

# ─── LangChain agent ──────────────────────────────────────────────────────────
tools = [move_servo, current_position, center_all, move_sequence, ask_clarification]

SYSTEM_PROMPT = """You are the controller of a physical robotic arm called Rupert.
You receive commands in natural language and convert them into precise servo movements.

══ ANATOMY AND DIRECTIONS ══

• base (servo 0) — horizontal torso rotation (5–175°)
    RIGHT  → SMALLER angle than 90° (e.g. 45°)
    LEFT   → LARGER angle than 90° (e.g. 135°)
    forward = 90°

• shoulder (servo 1) — raises and lowers the arm (5–160°)
    UP / RAISE / LIFT   → LARGER angle (e.g. 130°)
    DOWN / LOWER / DROP → SMALLER angle (e.g. 45°)
    horizontal = 90°

• elbow (servo 2) — extends and folds the forearm (5–175°)
    EXTEND / STRETCH / FORWARD / ADVANCE → LARGER angle (e.g. 135°)
    FOLD / RETRACT / BACK                → SMALLER angle (e.g. 45°)
    straight = 90°

• wrist (servo 3) — opens and closes the gripper (0–180°)
    OPEN  → SMALLER angle (0°)
    CLOSE → LARGER angle (180°)

• gripper (servo 4) — wrist rotation (0–180°; neutral=90°)

══ KEYWORD MAPPING ══

"up" / "raise" / "lift"                      → shoulder INCREASE angle
"down" / "lower" / "drop"                    → shoulder DECREASE angle
"extend" / "stretch" / "forward" / "advance" → elbow INCREASE angle
"fold" / "retract" / "back"                  → elbow DECREASE angle
"right"                                       → base DECREASE angle
"left"                                        → base INCREASE angle

IMPORTANT: "forward", "advance" refer to the ELBOW, never to the base.
IMPORTANT: "up" and "down" refer to the SHOULDER, never to the base.

══ SEQUENCE TO GRAB AN OBJECT ══

"grab" / "pick" / "grasp object in front":
  1. wrist → 0°     (open gripper)
  2. shoulder → 50° (lower arm)
  3. elbow → 135°   (extend to reach)
  4. wrist → 180°   (close gripper)

"release" / "drop" / "place":
  1. wrist → 0°     (open gripper)

══ RULES ══

1. ALWAYS use tools to execute — never just describe.
2. For multiple servos, prefer move_sequence.
3. NEVER move the base when receiving "forward", "up" or "down".
4. Briefly confirm in English what was executed.
5. If something is out of limits, execute the closest valid value and inform the user.
6. If the command is vague, creative, or has no clear servo mapping
   (e.g. "wave goodbye", "dance", "shake"), use ask_clarification BEFORE
   attempting any movement. Never guess in these cases."""

llm   = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0)
agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

# ─── Main loop ────────────────────────────────────────────────────────────────
history: list = []

print("═" * 55)
print("  Rupert — Natural Language Control")
print("  Type a command or 'quit' to exit.")
print("═" * 55)

send()
time.sleep(0.1)

try:
    while True:
        try:
            cmd = input("\nYou: ").strip()
        except EOFError:
            break

        if not cmd:
            continue
        if cmd.lower() in ("quit", "exit"):
            break

        history.append(HumanMessage(content=cmd))
        try:
            _stop_spin.clear()
            def spinner():
                chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
                i = 0
                while not _stop_spin.is_set():
                    print(f"\r  Thinking {chars[i % len(chars)]}", end="", flush=True)
                    i += 1
                    time.sleep(0.1)
                print("\r" + " " * 20 + "\r", end="", flush=True)
            t = threading.Thread(target=spinner, daemon=True)
            t.start()
            result = agent.invoke(
                {"messages": history},
                config={"recursion_limit": 8}
            )
            _stop_spin.set()
            t.join()
            output = result["messages"][-1].content
            print(f"\nRupert: {output}")
            history = result["messages"]
            if len(history) > 20:
                history = history[-20:]
        except Exception as e:
            _stop_spin.set()
            print(f"\n[Error] {e}")
            history.pop()

except KeyboardInterrupt:
    pass
finally:
    print("\nClosing serial connection...")
    ser.close()
    sys.exit(0)
