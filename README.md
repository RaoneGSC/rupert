# Rupert

Rupert is a 5-degree-of-freedom robotic arm, developed as the first robot of the [AxisMov](https://github.com/RaoneGSC/axismov) platform. The project integrates physics simulation, reinforcement learning training, and natural language control.

## Features

- **Dual simulation**: NVIDIA Isaac Sim and PyBullet
- **RL training**: Gymnasium environment with PPO (Stable Baselines 3)
- **Natural language control**: LangChain + Groq connected to physical hardware
- **MCP Server**: control the robot directly from Claude Desktop
- **Hardware**: 5x SG92R servos communicating via serial (Raspberry Pi Pico, 230400 baud)

## Structure

```
rupert/
├── src/
│   ├── brain/        # Control modules (Isaac Sim, PyBullet, PhysicalAI)
│   ├── training/     # Gymnasium environment and PPO training script
│   ├── mcp/          # MCP server for Claude Desktop
│   └── simulation/   # Simulation and test scripts
├── assets/
│   ├── meshes/       # 3D models (.stl)
│   └── usd/          # USD scenes for Isaac Sim
├── cfg/
│   └── urdf/         # Robot URDF descriptions
└── scripts/          # Utilities and serial communication tests
```

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/RaoneGSC/rupert.git
cd rupert

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

## Hardware

| Component | Details |
|---|---|
| Microcontroller | Raspberry Pi Pico |
| Servos | 5x SG92R |
| Communication | USB Serial, 230400 baud |
| Port | COM4 (configurable in scripts) |

## Usage

### Isaac Sim
Open Isaac Sim, load `assets/usd/IsaacRupert.usd` and run `src/brain/IsaacRupertBrain.py` in the script terminal.

### PyBullet simulation
```bash
python src/brain/RupertBrainV2.py
```

### RL training
```bash
python src/training/train.py
```

### Natural language control (physical hardware)
```bash
python src/brain/RupertPhysicalAI.py
```

### MCP Server (Claude Desktop)
```bash
python src/mcp/RupertMCP.py
```

## License

MIT
