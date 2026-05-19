# Rupert

<p align="center">
  <img src="docs/images/rupert_physical.png" width="420" alt="Rupert robotic arm"/>
</p>

> **Work in progress.** Rupert is an actively developed platform — control models, simulation, and hardware are continuously being improved. Expect rough edges.

Rupert is a 5-DOF robotic arm built from 3D-printed parts and off-the-shelf components, designed as a low-cost Physical AI testbed. It is the first robot of the [AxisMov](https://github.com/RaoneGSC/axismov) platform.

The main interest of the project is the **sim-to-real pipeline**: training or controlling the robot in simulation (NVIDIA Isaac Sim) and transferring that directly to the physical hardware via serial communication.

---

## Architecture

Rupert is split into two layers:

- **Brain** (`src/brain/`) — runs on the PC, handles simulation, AI, and high-level control
- **Firmware** (`firmware/`) — runs on the Raspberry Pi Pico 2, drives the servos directly

```
PC (Brain)  ──── USB Serial (230400 baud) ────  Pico 2 (Firmware)  ──── PWM ────  Servos
```

<p align="center">
  <img src="docs/images/architecture.jpg" width="800" alt="Rupert Architecture Diagram"/>
</p>

---

## Firmware — Peripheral Nervous System

`firmware/peripheral_system.py` is the MicroPython script that runs on the **Raspberry Pi Pico 2**. Flash it using [Thonny](https://thonny.org/) or `mpremote`.

It listens on USB serial for commands in the format:

```
angle0,angle1,angle2,angle3,angle4\n
```

And responds with:

```
OK,angle0,angle1,angle2,angle3,angle4
```

Or `ERR,FORMAT` / `ERR,<message>` on failure. On startup it prints `READY`.

| Pin | Joint | Servo | Notes |
|---|---|---|---|
| 15 | Base | SG92R | carbon fiber gears — handles higher torque |
| 14 | Shoulder | MG90S | metal gear — highest load area |
| 13 | Elbow | SG92R | carbon fiber gears — handles higher torque |
| 12 | Wrist | SG90 | opens/closes gripper |
| 19 | Gripper | SG90 | wrist rotation |

---

## Kinematics

Rupert is a **5-DOF serial manipulator** with the following joint chain:

| Joint | Index | Motion | Range | Servo |
|---|---|---|---|---|
| Base | 0 | Rotation (yaw) | 5° – 175° | SG92R |
| Shoulder | 1 | Pitch | 5° – 160° | MG90S |
| Elbow | 2 | Pitch | 5° – 175° | SG92R |
| Wrist | 3 | Roll | 0° – 180° | SG90 |
| Gripper | 4 | Open / Close | 0° – 180° | SG90 |

**Kinematic chain:**

```
World → Base (yaw) → Shoulder (pitch) → Elbow (pitch) → Wrist (roll) → Gripper (end-effector)
```

- **Base** rotates the entire arm horizontally around the Z axis (yaw)
- **Shoulder + Elbow** form a planar 2-DOF arm in the vertical plane, controlling reach and height via two pitch joints
- **Wrist** rolls the gripper assembly around the forearm axis, allowing orientation of the end-effector
- **Gripper** is a parallel jaw mechanism actuated by a single servo

The arm operates in a **polar coordinate workspace** — the base angle sets the azimuth, while shoulder and elbow angles define the position in the vertical plane. No inverse kinematics solver is currently implemented; control is done by direct joint angle commands.

---

## Brain Modules

Rupert has multiple control interfaces, each in `src/brain/`:

| File | Description |
|---|---|
| `IsaacRupertBrain.py` | **Main sim-to-real bridge** — reads joint positions from Isaac Sim and streams them to the Pico via serial |
| `IsaacBridgeScript.py` | **Isaac Sim TCP bridge** — paste into Isaac Script Editor; opens a socket on port 9877 so the MCP can control the simulation thread-safely |
| `RupertBrainV3.py` | Keyboard-based direct control of the physical robot |
| `RupertBrainPyBulletV2.py` | PyBullet simulation + serial bridge ⚠️ partial assembly (2-DOF only) |
| `RupertBrainPyBulletV1.py` | First PyBullet prototype ⚠️ partial assembly |
| `RupertPhysicalAI.py` | Natural language control via LangChain + Groq |

> ⚠️ The PyBullet scripts and RL training environment (`src/training/`) model a **partial, 2-DOF version** of Rupert, not the full 5-DOF assembly. Full-assembly RL training is on the roadmap.

---

## MCP Servers

Rupert exposes three [MCP](https://modelcontextprotocol.io/) servers that let Claude Desktop control the robot directly:

| File | Server name | Description |
|---|---|---|
| `src/mcp/RupertMCP.py` | `rupert` | Serial servo control — `move_servo`, `move_sequence`, `center_all`, `current_position` |
| `src/mcp/RupertVisionMCP.py` | `rupert-vision` | Webcam computer vision — captures frames Claude can see, monitors motion, detects Rupert position via blue mat anchor |
| `src/mcp/IsaacUSDMCP.py` | `isaac-usd` | Isaac Sim control — connects to `IsaacBridgeScript.py` running inside Isaac, exposes scene inspection and drive control |

### Claude Code slash commands

Three project-scoped commands live in `.claude/commands/`:

| Command | Description |
|---|---|
| `/rupert-mover <text>` | Interprets a natural-language movement command and executes it via the `rupert` MCP |
| `/rupert-visao [goal]` | Full vision-action loop: starts webcam, moves arm, waits for motion to stop, checks result visually, fine-tunes |
| `/rupert-calibrar` | Runs each servo through its full range with camera feedback, reports OK / problem per joint |

---

## Sim-to-Real with NVIDIA Isaac Sim

The most developed pipeline uses **Isaac Sim** as the simulation environment. The robot is controlled in simulation and commands are streamed to the physical hardware in real time.

**Requirements:** [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim) (6.0+)

### Step 1 — Open the scene

Launch Isaac Sim, go to **File → Open**, navigate to the `assets/usd/` folder and open `IsaacRupert.usd`.

<p align="center">
  <img src="docs/images/isaac_open_usd.png" width="700" alt="Opening IsaacRupert.usd in Isaac Sim"/>
</p>

### Step 2 — Flash the firmware

Flash `firmware/pico_servo_protected.py` to the Raspberry Pi Pico 2 using Thonny or `mpremote`. Connect the Pico via USB and confirm the COM port in `IsaacRupertBrain.py`.

### Step 3 — Run the brain script

Once the scene loads you should see Rupert in the viewport with all joints visible in the Physics Inspector.

<p align="center">
  <img src="docs/images/isaac_loaded.png" width="700" alt="Rupert loaded in Isaac Sim with joints inspector"/>
</p>

Open the **Script Editor** (bottom panel), load `src/brain/IsaacRupertBrain.py` and hit **Run (Ctrl+Enter)**.

The script will:
1. Connect to the Pico via serial (`COM4`, 230400 baud)
2. Start a smooth ramp from 90° to the current simulation position
3. Stream joint angles to the robot at 50Hz

### Step 4 (optional) — Enable Claude control via MCP

To let Claude Desktop control the simulation directly, also run `src/brain/IsaacBridgeScript.py` in the Script Editor. It opens a TCP socket on `localhost:9877` and exposes a thread-safe command queue so the `isaac-usd` MCP can inspect the scene and set drive targets without touching Isaac's USD APIs from the wrong thread.

Available bridge commands: `resumo`, `listar_prims`, `inspecionar`, `obter_juntas`, `buscar_prims`, `definir_drive`, `resetar_drives`, `articulacoes`.

---

## Computer Vision

Rupert uses a low-cost USB webcam as a visual sensor. Two components handle this:

- **`src/mcp/RupertVisionMCP.py`** — MCP server that returns `ImageContent` frames so Claude can see the robot directly. Supports continuous background monitoring, motion detection (frame-diff), and position detection.
- **`scripts/teste_visao_rupert.py`** — Standalone real-time test window (OpenCV). Run this to tune detection before using the MCP. Keyboard shortcuts: `O`=YOLO, `A`=ArUco, `M`=motion mask, `C`=debug masks, `S`=screenshot, `Q`=quit.

### Detection strategy

The robot sits on a **blue cutting mat** which acts as a position anchor:

1. Detect the blue-green mat via HSV segmentation (`H 78–115`)
2. Project the robot bounding-box above the mat
3. Confirm with SG90 servo blobs in the ROI (`H 95–140`)

If detection fails, use `calibrar_deteccao()` via the MCP (or press `C` in the test script) to see the HSV masks, then adjust thresholds with `ajustar_hsv_tapete()` at runtime.

---

## Hardware

Rupert is fully 3D-printable. All parts use **M3 screws**. STL and USD files are in `assets/`.

| Component | Details |
|---|---|
| Microcontroller | Raspberry Pi Pico 2 |
| Motor driver | [Kitronik Simply Robotics Motor Driver Board for Raspberry Pi Pico](https://kitronik.co.uk/products/5348-kitronik-simply-robotics-for-raspberry-pi-pico) |
| Base servo (pin 15) | SG92R — carbon fiber gears |
| Shoulder servo (pin 14) | MG90S — metal gear, highest load area |
| Elbow servo (pin 13) | SG92R — carbon fiber gears |
| Wrist servo (pin 12) | SG90 |
| Gripper servo (pin 19) | SG90 |
| Communication | USB Serial, 230400 baud |
| Fasteners | M3 screws |

---

## Known Issues

Rupert is a work in progress. These are the known limitations currently being addressed:

### Physical

- **Shoulder / Elbow torque** — Even with MG996R servos, the arm length generates more torque than the servos can handle. Movements in these joints are unreliable under load. Planned fix: shorten arm and forearm to reduce required torque.

- **Gripper grip strength** — The current gripper design does not hold objects reliably. For testing, use very lightweight objects (paper, foam). A redesigned gripper with better mechanical advantage is planned.

### Software / Simulation

- **Isaac Sim gripper joints** — The gripper joint connections in `IsaacRupert.usd` have structural issues that can crash the simulation depending on the movement. Needs a clean USD rebuild of the gripper assembly.

- **Ground constraint artifact** — The base is fixed to the ground plane to prevent tipping, which creates unnatural behavior in some poses. A proper base mass/inertia model is the correct fix.

- **PyBullet / RL is 2-DOF only** — The training environment and PyBullet scripts model a simplified 2-joint version of Rupert. Full 5-DOF RL environment is planned.

---

## Roadmap

- [x] **Isaac Sim MCP** — `IsaacUSDMCP.py` + `IsaacBridgeScript.py`: Claude can inspect the scene, read joints, and set drive targets directly from Claude Desktop
- [x] **Computer vision module** — `RupertVisionMCP.py`: webcam integration with blue-mat anchor detection, motion sensing, and `ImageContent` frames Claude can see natively; `scripts/teste_visao_rupert.py` for threshold tuning
- [ ] **Full 5-DOF RL environment** — Extend the Gymnasium environment to the complete arm assembly
- [ ] **Shorter arm/forearm** — Redesign to reduce torque on shoulder and elbow joints
- [ ] **Gripper redesign** — Better mechanical advantage for reliable grasping

---

## Setup

```bash
git clone https://github.com/RaoneGSC/rupert.git
cd rupert
pip install -r requirements.txt
cp .env.example .env   # add your API keys if using RupertPhysicalAI or Autogen
```

Flash the firmware to the Pico separately via Thonny or `mpremote copy firmware/peripheral_system.py :main.py`.

---

## License

MIT
