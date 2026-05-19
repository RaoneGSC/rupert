"""
IsaacBridgeScript.py — v2 (thread-safe)
Cole no Script Editor do Isaac Sim e execute.

ARQUITETURA:
  Thread TCP  →  _cmd_queue  →  _worker() no loop do Isaac  →  USD APIs

As chamadas USD (stage.Traverse, DriveAPI, etc.) só acontecem no worker
assíncrono, que roda no loop principal do Isaac — sem race conditions.

Para parar: execute  _running = False  no Script Editor.
Para reiniciar: re-execute o script inteiro.
"""
import asyncio
import concurrent.futures
import json
import queue
import socket
import threading
import traceback

import omni.usd
from pxr import Usd, UsdGeom, UsdPhysics

HOST = "localhost"
PORT = 9877

# ── Fila de comandos ────────────────────────────────────────────────────────────
# Thread TCP coloca (concurrent.futures.Future, cmd, args).
# _worker() lê e executa no loop do Isaac, depois seta o Future.
_cmd_queue: queue.Queue = queue.Queue()


# ── Helpers de acesso ao stage ─────────────────────────────────────────────────

def _stage():
    return omni.usd.get_context().get_stage()


def _prim_tipo(prim) -> str:
    t = prim.GetTypeName()
    return t if t else "Xform"


def _juntas_do_stage(stage) -> list[dict]:
    juntas = []
    for prim in stage.Traverse():
        info = None
        if prim.IsA(UsdPhysics.RevoluteJoint):
            j = UsdPhysics.RevoluteJoint(prim)
            info = {
                "tipo":       "RevoluteJoint",
                "eixo":       j.GetAxisAttr().Get() or "X",
                "limite_inf": j.GetLowerLimitAttr().Get(),
                "limite_sup": j.GetUpperLimitAttr().Get(),
            }
        elif prim.IsA(UsdPhysics.PrismaticJoint):
            j = UsdPhysics.PrismaticJoint(prim)
            info = {
                "tipo":       "PrismaticJoint",
                "eixo":       j.GetAxisAttr().Get() or "X",
                "limite_inf": j.GetLowerLimitAttr().Get(),
                "limite_sup": j.GetUpperLimitAttr().Get(),
            }
        elif prim.IsA(UsdPhysics.FixedJoint):
            info = {"tipo": "FixedJoint"}
        elif prim.IsA(UsdPhysics.SphericalJoint):
            info = {"tipo": "SphericalJoint"}
        elif prim.IsA(UsdPhysics.Joint):
            info = {"tipo": "Joint"}

        if info is not None:
            for token in ("angular", "linear"):
                drive = UsdPhysics.DriveAPI.Get(prim, token)
                if drive and drive.GetTargetPositionAttr().HasValue():
                    info[f"drive_{token}_target"]    = drive.GetTargetPositionAttr().Get()
                    info[f"drive_{token}_stiffness"] = drive.GetStiffnessAttr().Get()
                    info[f"drive_{token}_damping"]   = drive.GetDampingAttr().Get()
            body0 = prim.GetRelationship("physics:body0").GetTargets()
            body1 = prim.GetRelationship("physics:body1").GetTargets()
            info["body0"]   = str(body0[0]) if body0 else None
            info["body1"]   = str(body1[0]) if body1 else None
            info["caminho"] = str(prim.GetPath())
            info["nome"]    = prim.GetName()
            juntas.append(info)
    return juntas


def _info_prim(prim) -> dict:
    info = {
        "caminho":   str(prim.GetPath()),
        "nome":      prim.GetName(),
        "tipo":      _prim_tipo(prim),
        "ativo":     prim.IsActive(),
        "filhos":    [p.GetName() for p in prim.GetChildren()],
        "atributos": {},
        "apis":      [str(s) for s in prim.GetAppliedSchemas()],
    }
    for attr in prim.GetAttributes():
        val = attr.Get()
        if val is not None:
            try:
                info["atributos"][attr.GetName()] = str(val)
            except Exception:
                pass
    if prim.HasAPI(UsdPhysics.RigidBodyAPI):
        rb = UsdPhysics.RigidBodyAPI(prim)
        info["rigid_body"] = {"kinematic": rb.GetKinematicEnabledAttr().Get()}
    if prim.HasAPI(UsdPhysics.MassAPI):
        info["mass_kg"] = UsdPhysics.MassAPI(prim).GetMassAttr().Get()
    return info


# ── Handlers (executados SOMENTE pelo _worker no loop do Isaac) ─────────────────

def _cmd_resumo(args):
    stage = _stage()
    if not stage:
        return {"erro": "Nenhuma cena aberta no Isaac Sim"}
    todos = list(stage.Traverse())
    tipos: dict[str, int] = {}
    for p in todos:
        t = _prim_tipo(p)
        tipos[t] = tipos.get(t, 0) + 1
    return {
        "arquivo":     stage.GetRootLayer().realPath,
        "total_prims": len(todos),
        "tipos":       tipos,
        "raiz_filhos": [p.GetName() for p in stage.GetPseudoRoot().GetChildren()],
        "num_juntas":  len(_juntas_do_stage(stage)),
    }


def _cmd_listar_prims(args):
    stage  = _stage()
    filtro = args.get("tipo", "").lower()
    prims  = []
    for p in stage.Traverse():
        tipo = _prim_tipo(p)
        if filtro and filtro not in tipo.lower():
            continue
        prims.append({"caminho": str(p.GetPath()), "tipo": tipo, "nome": p.GetName()})
    return {"prims": prims, "total": len(prims)}


def _cmd_inspecionar(args):
    stage   = _stage()
    caminho = args.get("caminho", "")
    prim    = stage.GetPrimAtPath(caminho)
    if not prim or not prim.IsValid():
        return {"erro": f"Prim não encontrado: {caminho}"}
    return _info_prim(prim)


def _cmd_obter_juntas(args):
    return {"juntas": _juntas_do_stage(_stage())}


def _cmd_buscar_prims(args):
    stage = _stage()
    termo = args.get("termo", "").lower()
    found = []
    for p in stage.Traverse():
        if termo in p.GetName().lower() or termo in str(p.GetPath()).lower():
            found.append({"caminho": str(p.GetPath()), "tipo": _prim_tipo(p), "nome": p.GetName()})
    return {"encontrados": found, "total": len(found)}


def _cmd_definir_drive(args):
    stage   = _stage()
    caminho = args.get("caminho", "")
    valor   = float(args.get("valor", 0.0))
    token   = args.get("token", "angular")
    prim    = stage.GetPrimAtPath(caminho)
    if not prim or not prim.IsValid():
        return {"erro": f"Prim não encontrado: {caminho}"}
    drive = UsdPhysics.DriveAPI.Get(prim, token)
    if not drive:
        drive = UsdPhysics.DriveAPI.Apply(prim, token)
        drive.GetStiffnessAttr().Set(1e6)
        drive.GetDampingAttr().Set(1e4)
    drive.GetTargetPositionAttr().Set(valor)
    return {"ok": True, "junta": caminho, "token": token, "valor": valor}


def _cmd_resetar_drives(args):
    stage     = _stage()
    resetados = []
    for prim in stage.Traverse():
        for token in ("angular", "linear"):
            drive = UsdPhysics.DriveAPI.Get(prim, token)
            if drive and drive.GetTargetPositionAttr().HasValue():
                drive.GetTargetPositionAttr().Set(0.0)
                resetados.append(f"{prim.GetPath()}:{token}")
    return {"ok": True, "resetados": resetados}


def _cmd_articulacoes(args):
    stage  = _stage()
    raizes = []
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            corpos = [str(s.GetPath()) for s in Usd.PrimRange(prim)
                      if s.HasAPI(UsdPhysics.RigidBodyAPI)]
            raizes.append({"caminho": str(prim.GetPath()), "nome": prim.GetName(), "corpos": corpos})
    return {"articulacoes": raizes}


HANDLERS = {
    "resumo":         _cmd_resumo,
    "listar_prims":   _cmd_listar_prims,
    "inspecionar":    _cmd_inspecionar,
    "obter_juntas":   _cmd_obter_juntas,
    "buscar_prims":   _cmd_buscar_prims,
    "definir_drive":  _cmd_definir_drive,
    "resetar_drives": _cmd_resetar_drives,
    "articulacoes":   _cmd_articulacoes,
}


# ── Worker assíncrono — roda no loop do Isaac, executa USD com segurança ────────

async def _worker():
    print("[IsaacBridge] Worker v2 iniciado no loop do Isaac.", flush=True)
    while _running:
        # drena até 10 comandos por tick para não travar o loop
        for _ in range(10):
            try:
                fut, cmd, args = _cmd_queue.get_nowait()
            except queue.Empty:
                break
            if fut.done():
                continue
            try:
                handler = HANDLERS.get(cmd)
                result  = handler(args) if handler else \
                          {"erro": f"Comando desconhecido: '{cmd}'. Disponíveis: {list(HANDLERS)}"}
                fut.set_result(result)
            except Exception:
                fut.set_result({"erro": traceback.format_exc()})
        await asyncio.sleep(0.01)   # cede ao loop do Isaac entre ticks
    print("[IsaacBridge] Worker encerrado.", flush=True)


# ── Thread TCP — só faz I/O de socket, nunca toca USD ──────────────────────────

def _handle_client(conn: socket.socket):
    with conn:
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if data.endswith(b"\n"):
                    break
            msg  = json.loads(data.decode())
            cmd  = msg.get("cmd", "")
            args = msg.get("args", {})

            fut = concurrent.futures.Future()
            _cmd_queue.put((fut, cmd, args))

            try:
                resposta = fut.result(timeout=10.0)
            except concurrent.futures.TimeoutError:
                resposta = {"erro": "Timeout: Isaac Sim não processou o comando a tempo (10s)"}
            except Exception as e:
                resposta = {"erro": str(e)}

        except Exception:
            resposta = {"erro": traceback.format_exc()}

        try:
            conn.sendall((json.dumps(resposta, ensure_ascii=False) + "\n").encode())
        except Exception:
            pass


def _servidor():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(5)
    globals()["_server_socket"] = sock
    print(f"[IsaacBridge] TCP em {HOST}:{PORT} aguardando MCP...", flush=True)
    while _running:
        try:
            sock.settimeout(1.0)
            conn, _ = sock.accept()
            threading.Thread(target=_handle_client, args=(conn,), daemon=True).start()
        except socket.timeout:
            continue
        except Exception:
            break
    sock.close()
    print("[IsaacBridge] TCP encerrado.", flush=True)


# ── Inicialização (segura para re-execução no Script Editor) ───────────────────

_running = True

# Cancela worker anterior se existir
prev_task = globals().get("_BRIDGE_TASK")
if prev_task and not prev_task.done():
    prev_task.cancel()

# Inicia thread TCP (só se não houver uma rodando)
prev_thread = globals().get("_BRIDGE_THREAD")
if not prev_thread or not prev_thread.is_alive():
    t = threading.Thread(target=_servidor, daemon=True)
    t.start()
    globals()["_BRIDGE_THREAD"] = t
else:
    print("[IsaacBridge] Thread TCP já ativa, reutilizando.", flush=True)

# Inicia worker no loop do Isaac
loop = asyncio.get_event_loop()
task = loop.create_task(_worker())
globals()["_BRIDGE_TASK"] = task

print("[IsaacBridge] Bridge v2 pronta! Thread-safe. Para parar: _running = False", flush=True)
