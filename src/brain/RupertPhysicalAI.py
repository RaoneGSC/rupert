#!/usr/bin/env python3
# RupertPhysicalAI.py — Controle por linguagem natural com LangChain + Claude
import os, serial, time, sys, threading
from typing import List, Dict, Any
from langchain_groq import ChatGroq
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

# ─── API Key ──────────────────────────────────────────────────────────────────
if not os.environ.get("GROQ_API_KEY"):
    raise EnvironmentError("GROQ_API_KEY não definida. Crie um arquivo .env com a variável.")

# ─── Controle global do spinner ───────────────────────────────────────────────
_stop_spin = threading.Event()
_stop_spin.set()  # começa parado

# ─── Serial ───────────────────────────────────────────────────────────────────
PORTA = "COM4"
BAUD  = 230400
ser   = serial.Serial(PORTA, BAUD, timeout=0.2)

# ─── Estado ───────────────────────────────────────────────────────────────────
angles    = [90.0] * 5
last_sent = angles.copy()

# ─── Parâmetros (idênticos ao original) ───────────────────────────────────────
STEP_BASE = [5.0,  2.0,  5.0,  5.0,  5.0]
STEP_MAX  = [10.0, 4.0, 10.0, 10.0, 10.0]
ACCEL     = [2.0,  0.5,  2.0,  2.0,  2.0]
DELAY     = 0.05
DEADBAND  = 1.0
ANGLE_MIN = [5,   5,   5,   0,   0]
ANGLE_MAX = [175, 160, 175, 180, 180]

SERVOS = ["base", "ombro", "cotovelo", "pulso", "garra"]

# ─── Comunicação serial ────────────────────────────────────────────────────────
def enviar():
    cmd = ",".join(str(int(round(a))) for a in angles) + "\n"
    ser.write(cmd.encode())
    try:
        resp = ser.readline().decode().strip()
        if resp:
            print(f"  [Pico] {resp}")
    except Exception:
        pass

def mover_para(idx: int, alvo: float):
    """Interpolação suave até o ângulo alvo usando STEP_BASE."""
    alvo = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], alvo))
    step = STEP_BASE[idx]
    while abs(angles[idx] - alvo) > DEADBAND:
        diff = alvo - angles[idx]
        move = min(step, abs(diff)) * (1 if diff > 0 else -1)
        angles[idx] = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], angles[idx] + move))
        enviar()
        time.sleep(DELAY)

# ─── Ferramentas LangChain ─────────────────────────────────────────────────────
@tool
def mover_servo(servo: str, angulo: str) -> str:
    """Move um servo do robô para o ângulo especificado.

    Servos disponíveis e seus limites:
      - base      : 5–175°  | DIREITA=ângulo menor (ex:45°)  ESQUERDA=ângulo maior (ex:135°)  frente=90°
      - ombro     : 5–160°  | CIMA=ângulo maior (ex:130°)    BAIXO=ângulo menor (ex:45°)       horizontal=90°
      - cotovelo  : 5–175°  | ESTICA=ângulo maior (ex:135°)  DOBRA=ângulo menor (ex:45°)       reto=90°
      - pulso     : 0–180°  | ABRE garra=ângulo menor (0°)   FECHA garra=ângulo maior (180°)
      - garra     : 0–180°  | rotação do pulso/garra          neutro=90°

    Args:
        servo: nome do servo (base, ombro, cotovelo, pulso ou garra)
        angulo: ângulo destino em graus
    """
    servo = servo.lower().strip()
    if servo not in SERVOS:
        return f"Servo inválido '{servo}'. Escolha: {', '.join(SERVOS)}"
    idx  = SERVOS.index(servo)
    alvo = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], float(angulo)))
    print(f"  → {servo} → {alvo:.0f}°")
    mover_para(idx, alvo)
    return f"{servo} posicionado em {angles[idx]:.0f}°"

@tool
def posicao_atual() -> str:
    """Retorna a posição atual (em graus) de todos os servos do robô."""
    partes = [f"{SERVOS[i]}: {angles[i]:.0f}°" for i in range(5)]
    return "Posição atual → " + " | ".join(partes)

@tool
def centralizar() -> str:
    """Move todos os servos para 90° (posição central/neutra do robô)."""
    print("  → Centralizando todos os servos...")
    for i in range(5):
        mover_para(i, 90.0)
    return "Robô centralizado em 90° em todos os eixos."

@tool
def mover_sequencia(movimentos: List[Dict[str, Any]]) -> str:
    """Executa uma sequência de movimentos em múltiplos servos.

    Use esta ferramenta para comandos compostos que envolvem mais de um servo.

    Args:
        movimentos: lista de objetos {"servo": str, "angulo": float}
                    Exemplo: [{"servo": "base", "angulo": 120}, {"servo": "garra", "angulo": 0}]
    """
    resultados = []
    for m in movimentos:
        s = str(m.get("servo", "")).lower().strip()
        a = m.get("angulo")
        if s in SERVOS and a is not None:
            idx  = SERVOS.index(s)
            alvo = max(ANGLE_MIN[idx], min(ANGLE_MAX[idx], float(a)))
            print(f"  → {s} → {alvo:.0f}°")
            mover_para(idx, alvo)
            resultados.append(f"{s}={angles[idx]:.0f}°")
        else:
            resultados.append(f"ignorado: {m}")
    return "Sequência concluída: " + ", ".join(resultados)

@tool
def pedir_esclarecimento(pergunta: str) -> str:
    """Use esta ferramenta quando o comando for ambíguo ou não souber como executá-lo.
    Exibe a pergunta ao usuário e aguarda uma resposta.

    Args:
        pergunta: a dúvida ou pedido de esclarecimento para o usuário
    """
    _stop_spin.set()  # para o spinner antes de pedir input
    print(f"\n  Rupert: {pergunta}")
    resposta = input("  Você: ").strip()
    return f"Usuário respondeu: {resposta}"

# ─── Agente LangChain ──────────────────────────────────────────────────────────
ferramentas = [mover_servo, posicao_atual, centralizar, mover_sequencia, pedir_esclarecimento]

SYSTEM_PROMPT = """Você é o controlador de um braço robótico físico chamado Rupert.
Você recebe comandos em linguagem natural e os converte em movimentos precisos dos servos.

══ ANATOMIA E DIREÇÕES ══

• base (servo 0) — rotação horizontal do torso (5–175°)
    DIREITA  → ângulo MENOR que 90° (ex: 45°)
    ESQUERDA → ângulo MAIOR que 90° (ex: 135°)
    frente = 90°

• ombro (servo 1) — sobe e desce o braço (5–160°)
    CIMA / LEVANTA / SOBE  → ângulo MAIOR (ex: 130°)
    BAIXO / ABAIXA / DESCE → ângulo MENOR (ex: 45°)
    horizontal = 90°

• cotovelo (servo 2) — estica e dobra o antebraço (5–175°)
    ESTICA / ESTENDE / FRENTE / AVANÇA → ângulo MAIOR (ex: 135°)
    DOBRA / ENCOLHE / RECUA / ATRÁS    → ângulo MENOR (ex: 45°)
    reto = 90°

• pulso (servo 3) — abre e fecha a garra (0–180°)
    ABRE  → ângulo MENOR (0°)
    FECHA → ângulo MAIOR (180°)

• garra (servo 4) — rotação do pulso (0–180°; neutro=90°)

══ MAPEAMENTO DE PALAVRAS-CHAVE ══

"cima" / "levanta" / "sobe"              → ombro AUMENTA ângulo
"baixo" / "abaixa" / "desce"            → ombro DIMINUI ângulo
"estende" / "estica" / "frente" / "avança" → cotovelo AUMENTA ângulo
"dobra" / "encolhe" / "recua" / "atrás" → cotovelo DIMINUI ângulo
"direita"                                → base DIMINUI ângulo
"esquerda"                               → base AUMENTA ângulo

IMPORTANTE: "frente", "avançar" referem-se ao COTOVELO, nunca à base.
IMPORTANTE: "cima" e "baixo" referem-se ao OMBRO, nunca à base.

══ SEQUÊNCIA PARA PEGAR OBJETO ══

"pegue" / "agarre" / "pegar objeto à frente":
  1. pulso → 0°     (abre a garra)
  2. ombro → 50°    (desce o braço)
  3. cotovelo → 135° (estica para alcançar)
  4. pulso → 180°   (fecha a garra)

"largue" / "solte" / "deposite":
  1. pulso → 0°     (abre a garra)

══ REGRAS ══

1. SEMPRE use as ferramentas para executar — nunca apenas descreva.
2. Para múltiplos servos, prefira mover_sequencia.
3. NUNCA mova a base ao receber "para frente", "para cima" ou "para baixo".
4. Confirme brevemente em português o que foi executado.
5. Se algo estiver fora dos limites, execute o mais próximo e avise.
6. Se o comando for vago, criativo ou não tiver mapeamento claro para servos
   (ex: "dar tchau", "dançar", "acenar"), use pedir_esclarecimento ANTES de
   tentar executar qualquer movimento. Nunca adivinhe nesses casos."""

llm   = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0)
agent = create_react_agent(llm, ferramentas, prompt=SYSTEM_PROMPT)

# ─── Loop principal ────────────────────────────────────────────────────────────
historico: list = []

print("═" * 55)
print("  Rupert — Controle por Linguagem Natural")
print("  Digite um comando ou 'sair' para encerrar.")
print("═" * 55)

# posição inicial
enviar()
time.sleep(0.1)

try:
    while True:
        try:
            cmd = input("\nVocê: ").strip()
        except EOFError:
            break

        if not cmd:
            continue
        if cmd.lower() in ("sair", "exit", "quit"):
            break

        historico.append(HumanMessage(content=cmd))
        try:
            _stop_spin.clear()  # ativa o spinner
            def spinner():
                chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
                i = 0
                while not _stop_spin.is_set():
                    print(f"\r  Pensando {chars[i % len(chars)]}", end="", flush=True)
                    i += 1
                    time.sleep(0.1)
                print("\r" + " " * 20 + "\r", end="", flush=True)
            t = threading.Thread(target=spinner, daemon=True)
            t.start()
            resultado = agent.invoke(
                {"messages": historico},
                config={"recursion_limit": 8}
            )
            _stop_spin.set()
            t.join()
            output = resultado["messages"][-1].content
            print(f"\nRupert: {output}")
            historico = resultado["messages"]
            if len(historico) > 20:
                historico = historico[-20:]
        except Exception as e:
            _stop_spin.set()
            print(f"\n[Erro] {e}")
            historico.pop()  # remove a mensagem que falhou

except KeyboardInterrupt:
    pass
finally:
    print("\nEncerrando conexão serial...")
    ser.close()
    sys.exit(0)
