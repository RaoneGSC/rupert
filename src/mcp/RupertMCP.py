#!/usr/bin/env python3
# RupertMCP.py — Servidor MCP para controle do robô Rupert via Claude Desktop
import serial, time, sys
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP

# ─── Serial ───────────────────────────────────────────────────────────────────
PORTA = "COM4"
BAUD  = 230400
ser   = serial.Serial(PORTA, BAUD, timeout=0.2)

# ─── Estado ───────────────────────────────────────────────────────────────────
angles = [90.0] * 5

# ─── Parâmetros (idênticos ao RupertPhysicalAI) ───────────────────────────────
STEP_BASE = [5.0,  2.0,  5.0,  5.0,  5.0]
DELAY     = 0.05
DEADBAND  = 1.0
ANGLE_MIN = [5,   5,   5,   0,   0]
ANGLE_MAX = [175, 160, 175, 180, 180]
SERVOS    = ["base", "ombro", "cotovelo", "pulso", "garra"]
GRIP_IDX         = 4    # índice do servo de garra
GRIP_HOLD_OFFSET = 10   # graus extras para manter pressão de aperto

# ─── Comunicação serial ────────────────────────────────────────────────────────
def enviar():
    cmd_angles = angles.copy()
    g = cmd_angles[GRIP_IDX]
    if abs(g - 90) > 5:  # fora do neutro = está apertando algo
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

def mover_para(idx: int, alvo: float):
    alvo = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], alvo))
    dist = abs(alvo - angles[idx])
    if dist <= DEADBAND:
        return
    angles[idx] = alvo
    enviar()
    # espera proporcional à distância para o servo ter tempo de chegar
    time.sleep(max(0.4, dist * 0.025))

# ─── Servidor MCP ─────────────────────────────────────────────────────────────
mcp = FastMCP("Rupert")

@mcp.tool()
def mover_servo(servo: str, angulo: float) -> str:
    """Move um servo do robô para o ângulo especificado.

    Servos e direções corretas:
      - base      : DIREITA=ângulo menor (ex:45°)   ESQUERDA=ângulo maior (ex:135°)  frente=90°
      - ombro     : CIMA=ângulo maior (ex:130°)      BAIXO=ângulo menor (ex:45°)      horizontal=90°
      - cotovelo  : ESTICA=ângulo maior (ex:135°)    DOBRA=ângulo menor (ex:45°)      reto=90°
      - pulso     : ABRE garra=0°                    FECHA garra=180°
      - garra     : rotação do pulso/garra            neutro=90°

    Args:
        servo: nome do servo (base, ombro, cotovelo, pulso ou garra)
        angulo: ângulo destino em graus
    """
    servo = servo.lower().strip()
    if servo not in SERVOS:
        return f"Servo inválido '{servo}'. Use: {', '.join(SERVOS)}"
    idx  = SERVOS.index(servo)
    alvo = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], float(angulo)))
    print(f"→ {servo} → {alvo:.0f}°", flush=True, file=sys.stderr)
    mover_para(idx, alvo)
    return f"{servo} posicionado em {angles[idx]:.0f}°"

@mcp.tool()
def posicao_atual() -> str:
    """Retorna a posição atual em graus de todos os servos do robô."""
    partes = [f"{SERVOS[i]}: {angles[i]:.0f}°" for i in range(5)]
    return "Posição atual → " + " | ".join(partes)

@mcp.tool()
def centralizar() -> str:
    """Move todos os servos para 90° (posição central/neutra do robô)."""
    print("→ Centralizando...", flush=True, file=sys.stderr)
    for i in range(5):
        mover_para(i, 90.0)
    return "Robô centralizado em 90° em todos os eixos."

@mcp.tool()
def mover_sequencia(movimentos: List[Dict[str, Any]]) -> str:
    """Executa uma sequência de movimentos em múltiplos servos.

    Use para comandos que envolvem mais de um servo ao mesmo tempo.

    Args:
        movimentos: lista de objetos {"servo": str, "angulo": float}
                    Exemplo: [{"servo": "ombro", "angulo": 130}, {"servo": "pulso", "angulo": 0}]
    """
    resultados = []
    for m in movimentos:
        s = str(m.get("servo", "")).lower().strip()
        a = m.get("angulo")
        if s in SERVOS and a is not None:
            idx  = SERVOS.index(s)
            alvo = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], float(a)))
            print(f"→ {s} → {alvo:.0f}°", flush=True, file=sys.stderr)
            mover_para(idx, alvo)
            resultados.append(f"{s}={angles[idx]:.0f}°")
        else:
            resultados.append(f"ignorado: {m}")
    return "Sequência concluída: " + ", ".join(resultados)

# ─── Inicialização ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Rupert MCP Server iniciando...", flush=True, file=sys.stderr)
    enviar()
    time.sleep(0.1)
    print("Pronto. Aguardando Claude Desktop.", flush=True, file=sys.stderr)
    mcp.run()
