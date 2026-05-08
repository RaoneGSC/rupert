# Rupert

<p align="center">
  <img src="docs/images/rupert_physical.jpg" width="420" alt="Rupert robotic arm"/>
</p>

> **Work in progress.** Rupert is an actively developed platform — control models, simulation, and hardware are continuously being improved. Expect rough edges.

Rupert is a 5-DOF robotic arm built from 3D-printed parts and off-the-shelf components, designed as a low-cost Physical AI testbed. It is the first robot of the [AxisMov](https://github.com/RaoneGSC/axismov) platform.

The main interest of the project is the **sim-to-real pipeline**: training or controlling the robot in simulation (NVIDIA Isaac Sim) and transferring that directly to the physical hardware via serial communication.

---

## Brain Modules

Rupert has multiple control interfaces, each in `src/brain/`:

| File | Description |
|---|---|
| `IsaacRupertBrain.py` | **Main sim-to-real bridge** — reads joint positions from Isaac Sim and sends them to the physical robot via serial |
| `RupertBrainV3.py` | Keyboard-based direct control of the physical robot |
| `RupertBrainPyBulletV2.py` | PyBullet simulation + serial bridge (2-DOF) |
| `RupertBrainPyBulletV1.py` | First PyBullet prototype |
| `RupertPhysicalAI.py` | Natural language control via LangChain + Groq |
| `src/mcp/RupertMCP.py` | MCP server — control Rupert directly from Claude Desktop |

---

## Sim-to-Real with NVIDIA Isaac Sim

The most developed pipeline uses **Isaac Sim** as the simulation environment. The robot is controlled in simulation and commands are streamed to the physical hardware in real time.

**Requirements:** [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim) (6.0+)

### Step 1 — Open the scene

Launch Isaac Sim, go to **File → Open**, navigate to the `assets/usd/` folder and open `IsaacRupert.usd`.

<p align="center">
  <img src="docs/images/isaac_open_usd.png" width="700" alt="Opening IsaacRupert.usd in Isaac Sim"/>
</p>

### Step 2 — Load the robot and run the brain

Once the scene loads you should see Rupert in the viewport with all joints visible in the Physics Inspector.

<p align="center">
  <img src="docs/images/isaac_loaded.png" width="700" alt="Rupert loaded in Isaac Sim with joints inspector"/>
</p>

Open the **Script Editor** (bottom panel), load `src/brain/IsaacRupertBrain.py` and hit **Run (Ctrl+Enter)**.

The script will:
1. Connect to the physical robot via serial (`COM4`, 230400 baud)
2. Start a smooth ramp from 90° to the current simulation position
3. Stream joint angles to the robot at 50Hz

> Make sure the Raspberry Pi Pico is connected and the correct COM port is set in `IsaacRupertBrain.py`.

---

## Hardware

Rupert is fully 3D-printable. All parts use **M3 screws**. STL and USD files are in `assets/`.

| Component | Details |
|---|---|
| Microcontroller | Raspberry Pi Pico 2 |
| Motor driver | [Kitronik Simply Robotics Motor Driver Board for Raspberry Pi Pico](https://kitronik.co.uk/products/5331-simply-robotics-motor-driver-board-for-raspberry-pi-pico) |
| Servos (base, wrist, gripper) | SG92R — 9g micro servo |
| Servos (shoulder, elbow) | MG996R — metal gear, higher torque |
| Communication | USB Serial, 230400 baud |
| Fasteners | M3 screws |

---

## Known Issues & Roadmap

Rupert is a work in progress. These are the known limitations currently being addressed:

### Physical

- **Shoulder / Elbow torque** — Even with MG996R servos, the arm length generates more torque than the servos can handle. Current movements in these joints are unreliable under load. The planned fix is to shorten the arm and forearm segments to reduce the required torque.

- **Gripper grip strength** — The current gripper design does not hold objects reliably. For testing, use very lightweight objects (paper, foam). A redesigned gripper with better mechanical advantage is planned.

### Software / Simulation

- **Isaac Sim gripper joints** — The gripper joint connections in `IsaacRupert.usd` have structural issues. Depending on the movement, they can cause the simulation to crash. Needs a clean URDF/USD rebuild of the gripper assembly.

- **Ground constraint artifact** — To prevent Rupert from tipping over in simulation, the base is fixed to the ground plane. This creates unnatural behavior in some poses. A proper base mass/inertia model is the correct fix.

---

## Setup

```bash
git clone https://github.com/RaoneGSC/rupert.git
cd rupert
pip install -r requirements.txt
cp .env.example .env   # add your API keys if using RupertPhysicalAI or Autogen
```

---

## License

MIT
