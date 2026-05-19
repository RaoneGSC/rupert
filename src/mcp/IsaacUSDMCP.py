#!/usr/bin/env python3
"""
IsaacUSDMCP.py — MCP para inspecionar e controlar a cena aberta no Isaac Sim.

Pré-requisito: IsaacBridgeScript.py deve estar rodando dentro do Isaac Sim
(cole no Script Editor e execute). Ele abre um socket TCP em localhost:9877.
"""
import json
import socket
import sys
from typing import Optional

import mcp.types as mcp_types
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("isaac-usd")

HOST = "localhost"
PORT = 9877
TIMEOUT = 8.0


# ── Comunicação com o bridge ────────────────────────────────────────────────────

def _enviar(cmd: str, args: dict = {}) -> dict:
    """Envia um comando ao IsaacBridgeScript e retorna a resposta."""
    try:
        with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as s:
            msg = json.dumps({"cmd": cmd, "args": args}, ensure_ascii=False) + "\n"
            s.sendall(msg.encode())
            data = b""
            while True:
                chunk = s.recv(8192)
                if not chunk:
                    break
                data += chunk
                if data.endswith(b"\n"):
                    break
        return json.loads(data.decode())
    except ConnectionRefusedError:
        return {
            "erro": (
                f"Não foi possível conectar ao Isaac Sim ({HOST}:{PORT}). "
                "Verifique se o IsaacBridgeScript.py está rodando no Script Editor."
            )
        }
    except Exception as e:
        return {"erro": f"Erro de comunicação: {e}"}


def _resultado_texto(r: dict) -> list[mcp_types.TextContent]:
    if "erro" in r:
        return [mcp_types.TextContent(type="text", text=f"Erro: {r['erro']}")]
    return [mcp_types.TextContent(type="text", text=json.dumps(r, indent=2, ensure_ascii=False))]


# ── Tools MCP ───────────────────────────────────────────────────────────────────

@mcp.tool()
def resumo_cena() -> list[mcp_types.TextContent]:
    """Retorna um resumo da cena aberta no Isaac Sim: arquivo, total de prims,
    tipos de objetos e número de juntas físicas.

    Use sempre primeiro para confirmar que o Isaac Sim está conectado e
    entender o que está na cena.
    """
    r = _enviar("resumo")
    if "erro" in r:
        return _resultado_texto(r)

    linhas = [
        f"Arquivo: {r.get('arquivo', 'desconhecido')}",
        f"Total de prims: {r.get('total_prims', 0)}",
        f"Juntas físicas: {r.get('num_juntas', 0)}",
        "",
        "Tipos na cena:",
    ]
    for tipo, qtd in sorted(r.get("tipos", {}).items(), key=lambda x: -x[1]):
        linhas.append(f"  {tipo}: {qtd}")
    linhas += ["", "Filhos da raiz:"] + [f"  /{n}" for n in r.get("raiz_filhos", [])]
    return [mcp_types.TextContent(type="text", text="\n".join(linhas))]


@mcp.tool()
def listar_prims(tipo_filtro: str = "") -> list[mcp_types.TextContent]:
    """Lista todos os prims da cena, com tipo e caminho.

    Args:
        tipo_filtro: filtra por tipo (ex: "Joint", "Mesh", "Xform"). Vazio = todos.
    """
    r = _enviar("listar_prims", {"tipo": tipo_filtro})
    if "erro" in r:
        return _resultado_texto(r)

    prims = r.get("prims", [])
    linhas = [f"Total: {r['total']} prims" + (f" (filtro: '{tipo_filtro}')" if tipo_filtro else ""), ""]
    for p in prims:
        linhas.append(f"{p['caminho']}  [{p['tipo']}]")
    return [mcp_types.TextContent(type="text", text="\n".join(linhas))]


@mcp.tool()
def inspecionar_prim(caminho: str) -> list[mcp_types.TextContent]:
    """Inspeciona um prim específico em detalhe: atributos, APIs aplicadas,
    rigid body, massa, filhos.

    Args:
        caminho: caminho USD do prim (ex: /World/Rupert/base)
    """
    return _resultado_texto(_enviar("inspecionar", {"caminho": caminho}))


@mcp.tool()
def obter_juntas() -> list[mcp_types.TextContent]:
    """Lista todas as juntas físicas da cena com tipo, eixo, limites de ângulo,
    corpos conectados e drive targets atuais.

    Equivalente a abrir o Physics Inspector e ver todas as juntas de uma vez.
    """
    r = _enviar("obter_juntas")
    if "erro" in r:
        return _resultado_texto(r)

    juntas = r.get("juntas", [])
    if not juntas:
        return [mcp_types.TextContent(type="text", text="Nenhuma junta física encontrada na cena.")]

    linhas = [f"Juntas encontradas: {len(juntas)}", ""]
    for j in juntas:
        linhas.append(f"{'─'*60}")
        linhas.append(f"Nome:    {j['nome']}")
        linhas.append(f"Tipo:    {j['tipo']}")
        linhas.append(f"Caminho: {j['caminho']}")
        if "eixo" in j:
            linhas.append(f"Eixo:    {j['eixo']}")
        if j.get("limite_inf") is not None:
            linhas.append(f"Limites: {j['limite_inf']:.1f}° → {j['limite_sup']:.1f}°")
        if j.get("body0"):
            linhas.append(f"Body0:   {j['body0']}")
        if j.get("body1"):
            linhas.append(f"Body1:   {j['body1']}")
        for token in ("angular", "linear"):
            key = f"drive_{token}_target"
            if key in j:
                linhas.append(
                    f"Drive {token}: target={j[key]:.2f}  "
                    f"stiffness={j.get(f'drive_{token}_stiffness', '?')}  "
                    f"damping={j.get(f'drive_{token}_damping', '?')}"
                )
        linhas.append("")
    return [mcp_types.TextContent(type="text", text="\n".join(linhas))]


@mcp.tool()
def articulacoes() -> list[mcp_types.TextContent]:
    """Lista as raízes de articulação da cena e seus corpos rígidos.

    Útil para entender a hierarquia do robô — qual prim é a raiz,
    quais são os elos (links) conectados.
    """
    r = _enviar("articulacoes")
    if "erro" in r:
        return _resultado_texto(r)

    arts = r.get("articulacoes", [])
    if not arts:
        return [mcp_types.TextContent(type="text", text="Nenhuma articulação encontrada.")]

    linhas = [f"Articulações: {len(arts)}", ""]
    for a in arts:
        linhas.append(f"Raiz: {a['caminho']}")
        for corpo in a.get("corpos", []):
            linhas.append(f"  └─ {corpo}")
        linhas.append("")
    return [mcp_types.TextContent(type="text", text="\n".join(linhas))]


@mcp.tool()
def buscar_prims(termo: str) -> list[mcp_types.TextContent]:
    """Busca prims na cena pelo nome ou caminho.

    Args:
        termo: texto a buscar (case-insensitive) no nome ou caminho do prim.
    """
    r = _enviar("buscar_prims", {"termo": termo})
    if "erro" in r:
        return _resultado_texto(r)

    encontrados = r.get("encontrados", [])
    linhas = [f"'{termo}' → {r['total']} resultado(s)", ""]
    for p in encontrados:
        linhas.append(f"{p['caminho']}  [{p['tipo']}]")
    return [mcp_types.TextContent(type="text", text="\n".join(linhas))]


@mcp.tool()
def definir_drive_junta(caminho: str, valor: float, token: str = "angular") -> list[mcp_types.TextContent]:
    """Move uma junta definindo o drive target — equivalente a arrastar o
    slider no Physics Inspector do Isaac Sim.

    Para RevoluteJoint: valor em graus.
    Para PrismaticJoint: valor em metros (use token="linear").

    Exemplo: definir_drive_junta("/World/Rupert/base_joint", 45.0)

    Args:
        caminho: caminho USD da junta (ex: /World/Rupert/shoulder_joint)
        valor:   ângulo em graus (revoluta) ou metros (prismática)
        token:   "angular" para juntas rotativas, "linear" para prismáticas
    """
    r = _enviar("definir_drive", {"caminho": caminho, "valor": valor, "token": token})
    return _resultado_texto(r)


@mcp.tool()
def resetar_todas_juntas() -> list[mcp_types.TextContent]:
    """Reseta o drive target de todas as juntas para 0.

    Equivale a voltar todos os sliders do Physics Inspector para zero.
    """
    r = _enviar("resetar_drives")
    if "erro" in r:
        return _resultado_texto(r)

    resetados = r.get("resetados", [])
    linhas = [f"Drives resetados: {len(resetados)}", ""] + resetados
    return [mcp_types.TextContent(type="text", text="\n".join(linhas))]


@mcp.tool()
def status_conexao_isaac() -> list[mcp_types.TextContent]:
    """Verifica se o IsaacBridgeScript está rodando no Isaac Sim e retorna
    informações básicas da cena.

    Use para confirmar que a conexão está ativa antes de qualquer outro comando.
    """
    r = _enviar("resumo")
    if "erro" in r:
        return [mcp_types.TextContent(
            type="text",
            text=(
                f"Isaac Sim NÃO conectado.\n{r['erro']}\n\n"
                "Para conectar:\n"
                "1. Abra o Isaac Sim\n"
                "2. Window → Script Editor\n"
                "3. Cole e execute o IsaacBridgeScript.py"
            ),
        )]
    return [mcp_types.TextContent(
        type="text",
        text=(
            f"Isaac Sim CONECTADO\n"
            f"Arquivo: {r.get('arquivo', '?')}\n"
            f"Prims: {r.get('total_prims', 0)} | Juntas: {r.get('num_juntas', 0)}"
        ),
    )]


# ── Inicialização ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Isaac USD MCP Server iniciando...", flush=True, file=sys.stderr)
    print(f"Aguardando conexões de Claude Desktop.", flush=True, file=sys.stderr)
    print(f"Isaac Sim bridge esperada em {HOST}:{PORT}", flush=True, file=sys.stderr)
    mcp.run()
