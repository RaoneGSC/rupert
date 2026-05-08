# Rupert

Rupert é um braço robótico de 5 graus de liberdade, desenvolvido como o primeiro robô da plataforma [AxisMov](https://github.com/AxisMov/axismov). O projeto integra simulação física, treinamento por aprendizado por reforço e controle por linguagem natural.

## Funcionalidades

- **Simulação dupla**: NVIDIA Isaac Sim e PyBullet
- **Treinamento RL**: ambiente Gymnasium com PPO (Stable Baselines 3)
- **Controle via linguagem natural**: LangChain + Groq conectado ao hardware físico
- **MCP Server**: controle do robô diretamente pelo Claude Desktop
- **Hardware**: 5 servos SG92R comunicando via serial (Raspberry Pi Pico, 230400 baud)

## Estrutura

```
rupert/
├── src/
│   ├── brain/        # Módulos de controle (Isaac Sim, PyBullet, PhysicalAI)
│   ├── training/     # Ambiente Gymnasium e script de treinamento PPO
│   ├── mcp/          # Servidor MCP para Claude Desktop
│   └── simulation/   # Scripts de simulação e testes
├── assets/
│   ├── meshes/       # Modelos 3D (.stl)
│   └── usd/          # Cenas USD para Isaac Sim
├── cfg/
│   └── urdf/         # Descrições URDF do robô
└── scripts/          # Utilitários e testes de comunicação serial
```

## Setup

```bash
# 1. Clone o repositório
git clone https://github.com/AxisMov/rupert.git
cd rupert

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas chaves de API
```

## Hardware

| Componente | Detalhe |
|---|---|
| Microcontrolador | Raspberry Pi Pico |
| Servos | 5x SG92R |
| Comunicação | Serial USB, 230400 baud, COM4 |
| Porta | COM4 (configurável nos scripts) |

## Uso

### Simulação com Isaac Sim
Abra o Isaac Sim, carregue `assets/usd/IsaacRupert.usd` e execute `src/brain/IsaacRupertBrain.py` no terminal de script.

### Simulação com PyBullet
```bash
python src/brain/RupertBrainV2.py
```

### Treinamento RL
```bash
python src/training/train.py
```

### Controle por linguagem natural (hardware físico)
```bash
python src/brain/RupertPhysicalAI.py
```

### MCP Server (Claude Desktop)
```bash
python src/mcp/RupertMCP.py
```

## Licença

MIT
