#!/usr/bin/env python3
# RupertVisionMCP.py — Servidor MCP de visão para monitorar o Rupert via webcam
import base64
import io
import sys
import threading
import time
from datetime import datetime
from typing import Optional

import cv2
import mcp.types as mcp_types
import numpy as np
from PIL import Image
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rupert-vision")

# ─── Estado global ─────────────────────────────────────────────────────────────
_camera: Optional[cv2.VideoCapture] = None
_camera_index: int = 0
_ultimo_frame: Optional[np.ndarray] = None
_monitorando: bool = False
_thread_monitor: Optional[threading.Thread] = None
_historico_movimento: list[float] = []
_total_frames: int = 0
_lock = threading.Lock()


# ─── Helpers internos ──────────────────────────────────────────────────────────
def _abrir_camera(index: int = 0) -> cv2.VideoCapture:
    global _camera, _camera_index
    if _camera is not None and _camera.isOpened() and _camera_index == index:
        return _camera
    if _camera is not None:
        _camera.release()
    cam = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(index)
    if not cam.isOpened():
        raise RuntimeError(f"Não foi possível abrir câmera {index}")
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    _camera = cam
    _camera_index = index
    return cam


def _frame_para_base64(frame: np.ndarray, qualidade: int = 80) -> str:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=qualidade)
    return base64.b64encode(buf.getvalue()).decode()


def _diferenca_percentual(a: np.ndarray, b: np.ndarray) -> float:
    """Retorna % de pixels que mudaram mais de 15 pontos entre dois frames."""
    diff = cv2.absdiff(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY),
                       cv2.cvtColor(b, cv2.COLOR_BGR2GRAY))
    changed = np.sum(diff > 15)
    return 100.0 * changed / diff.size


def _loop_monitoramento(intervalo_s: float, camera_index: int):
    global _ultimo_frame, _monitorando, _historico_movimento, _total_frames
    try:
        cam = _abrir_camera(camera_index)
        frame_anterior = None
        while _monitorando:
            ok, frame = cam.read()
            if not ok:
                time.sleep(intervalo_s)
                continue
            with _lock:
                _ultimo_frame = frame.copy()
                _total_frames += 1
                if frame_anterior is not None:
                    diff = _diferenca_percentual(frame_anterior, frame)
                    _historico_movimento.append(diff)
                frame_anterior = frame.copy()
            time.sleep(intervalo_s)
    except Exception as e:
        print(f"[rupert-vision] Erro no monitoramento: {e}", file=sys.stderr)
    finally:
        _monitorando = False


# ─── Tools MCP ─────────────────────────────────────────────────────────────────
@mcp.tool()
def capturar_frame(
    camera_index: int = 0, qualidade: int = 80
) -> list[mcp_types.TextContent | mcp_types.ImageContent]:
    """Captura um frame da webcam e envia a foto para Claude ver o Rupert.

    Retorna tanto a imagem visual (Claude pode ver diretamente) quanto
    metadados de texto com dimensões e timestamp.

    Args:
        camera_index: índice da câmera (0 = câmera padrão)
        qualidade: qualidade JPEG 1-100 (padrão 80)
    """
    try:
        cam = _abrir_camera(camera_index)
        # descarta 3 frames para a câmera ajustar exposição
        for _ in range(3):
            cam.read()
        ok, frame = cam.read()
        if not ok:
            return [mcp_types.TextContent(type="text", text="Erro: não foi possível capturar frame da câmera")]
        with _lock:
            global _ultimo_frame
            _ultimo_frame = frame.copy()
        h, w = frame.shape[:2]
        ts = datetime.now().strftime("%H:%M:%S")
        b64 = _frame_para_base64(frame, qualidade)
        return [
            mcp_types.TextContent(type="text", text=f"Foto capturada — {w}x{h}px | {ts}"),
            mcp_types.ImageContent(type="image", data=b64, mimeType="image/jpeg"),
        ]
    except Exception as e:
        return [mcp_types.TextContent(type="text", text=f"Erro ao capturar frame: {e}")]


@mcp.tool()
def iniciar_monitoramento(intervalo_s: float = 1.0, camera_index: int = 0) -> str:
    """Inicia monitoramento contínuo da webcam em background.

    Captura frames em loop com o intervalo especificado. Use obter_frame_atual()
    para buscar o frame mais recente sem latência de abertura de câmera.
    Use aguardar_movimento_parar() para detectar quando o Rupert parou de se mover.

    Args:
        intervalo_s: intervalo entre capturas em segundos (padrão 1.0)
        camera_index: índice da câmera (0 = câmera padrão)
    """
    global _monitorando, _thread_monitor, _historico_movimento, _total_frames

    if _monitorando:
        return "Monitoramento já está em execução. Use parar_monitoramento() primeiro."

    _historico_movimento.clear()
    _total_frames = 0
    _monitorando = True

    _thread_monitor = threading.Thread(
        target=_loop_monitoramento,
        args=(intervalo_s, camera_index),
        daemon=True,
    )
    _thread_monitor.start()
    time.sleep(0.5)  # deixa a thread abrir a câmera

    if _monitorando:
        return (
            f"Monitoramento iniciado. Capturando a cada {intervalo_s}s. "
            f"Use obter_frame_atual() para ver o Rupert, "
            f"ou aguardar_movimento_parar() para esperar ele parar."
        )
    return "Erro ao iniciar monitoramento — verifique se a câmera está disponível."


@mcp.tool()
def parar_monitoramento() -> str:
    """Para o monitoramento contínuo da webcam e retorna estatísticas.

    Returns:
        Resumo com total de frames capturados e média de movimento detectado.
    """
    global _monitorando, _camera

    if not _monitorando:
        return "Monitoramento não está em execução."

    _monitorando = False
    if _thread_monitor is not None:
        _thread_monitor.join(timeout=3.0)

    total = _total_frames
    media_mov = (
        sum(_historico_movimento) / len(_historico_movimento)
        if _historico_movimento
        else 0.0
    )

    if _camera is not None:
        _camera.release()
        _camera = None

    return (
        f"Monitoramento parado. "
        f"Total de frames: {total} | "
        f"Movimento médio detectado: {media_mov:.2f}% de pixels alterados."
    )


@mcp.tool()
def obter_frame_atual(
    qualidade: int = 80,
) -> list[mcp_types.TextContent | mcp_types.ImageContent]:
    """Retorna a foto mais recente capturada pelo monitoramento.

    Mais rápido que capturar_frame() pois não abre a câmera de novo.
    Requer que iniciar_monitoramento() tenha sido chamado antes.

    Args:
        qualidade: qualidade JPEG 1-100 (padrão 80)
    """
    with _lock:
        frame = _ultimo_frame.copy() if _ultimo_frame is not None else None

    if frame is None:
        return [mcp_types.TextContent(
            type="text",
            text="Nenhum frame disponível. Chame iniciar_monitoramento() ou capturar_frame() primeiro.",
        )]

    h, w = frame.shape[:2]
    ts = datetime.now().strftime("%H:%M:%S")
    mov = _historico_movimento[-1] if _historico_movimento else None
    info = f"Frame atual — {w}x{h}px | {ts}"
    if mov is not None:
        info += f" | Movimento recente: {mov:.1f}%"
    return [
        mcp_types.TextContent(type="text", text=info),
        mcp_types.ImageContent(type="image", data=_frame_para_base64(frame, qualidade), mimeType="image/jpeg"),
    ]


@mcp.tool()
def aguardar_movimento_parar(
    timeout_s: float = 8.0, limiar_pixels: float = 2.0
) -> list[mcp_types.TextContent | mcp_types.ImageContent]:
    """Aguarda até que o Rupert pare de se mover (frames estabilizem).

    Bloqueia até que a diferença entre frames consecutivos caia abaixo de
    limiar_pixels% — sinaliza que o servo chegou na posição final.
    Requer que iniciar_monitoramento() esteja ativo.

    Use no loop de feedback visual:
      1. mover_servo() via MCP rupert
      2. aguardar_movimento_parar()  ← espera o servo chegar
      3. obter_frame_atual()         ← vê resultado
      4. Analisa e corrige se necessário

    Args:
        timeout_s: tempo máximo de espera em segundos (padrão 8.0)
        limiar_pixels: % mínima de pixels alterados para considerar "parado" (padrão 2.0)

    Returns:
        dict com parou (bool), tempo_decorrido (float) e frame_final_base64 (str)
    """
    if not _monitorando:
        return [mcp_types.TextContent(
            type="text",
            text="Erro: monitoramento não está ativo. Chame iniciar_monitoramento() primeiro.",
        )]

    inicio = time.time()
    estavel_count = 0  # quantas leituras consecutivas abaixo do limiar

    while time.time() - inicio < timeout_s:
        time.sleep(0.2)
        if len(_historico_movimento) >= 2:
            ultima_diff = _historico_movimento[-1]
            if ultima_diff < limiar_pixels:
                estavel_count += 1
                if estavel_count >= 3:  # 3 leituras estáveis consecutivas
                    break
            else:
                estavel_count = 0

    decorrido = time.time() - inicio
    parou = estavel_count >= 3

    with _lock:
        frame = _ultimo_frame.copy() if _ultimo_frame is not None else None

    mov_final = _historico_movimento[-1] if _historico_movimento else None
    status = "PAROU" if parou else f"TIMEOUT após {timeout_s}s"
    info = (
        f"{status} | Tempo: {round(decorrido, 2)}s | "
        f"Movimento final: {mov_final:.1f}%" if mov_final is not None
        else f"{status} | Tempo: {round(decorrido, 2)}s"
    )
    if not parou:
        info += " | Rupert pode ainda estar em movimento ou limiar muito baixo."

    conteudo: list[mcp_types.TextContent | mcp_types.ImageContent] = [
        mcp_types.TextContent(type="text", text=info)
    ]
    if frame is not None:
        conteudo.append(
            mcp_types.ImageContent(type="image", data=_frame_para_base64(frame), mimeType="image/jpeg")
        )
    return conteudo


# ─── Detecção do Rupert (tapete azul como âncora) ─────────────────────────────
_tapete_hsv_lo = np.array([ 78,  50,  30])
_tapete_hsv_hi = np.array([115, 255, 200])
_servo_hsv_lo  = np.array([ 95,  70,  50])
_servo_hsv_hi  = np.array([140, 255, 220])
_TAPETE_AREA_MIN = 4000
_SERVO_BLOB_MIN  = 40
_SERVO_BLOB_MAX  = 1800


def _detectar_rupert(frame: np.ndarray) -> dict | None:
    h, w = frame.shape[:2]
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask_tap = cv2.inRange(hsv, _tapete_hsv_lo, _tapete_hsv_hi)
    mask_tap = cv2.morphologyEx(mask_tap, cv2.MORPH_OPEN,  np.ones((5,  5),  np.uint8))
    mask_tap = cv2.morphologyEx(mask_tap, cv2.MORPH_CLOSE, np.ones((20, 20), np.uint8))

    cnts, _ = cv2.findContours(mask_tap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts    = [c for c in cnts if cv2.contourArea(c) >= _TAPETE_AREA_MIN]
    if not cnts:
        return None

    tapete        = max(cnts, key=cv2.contourArea)
    tx, ty, tw, th_t = cv2.boundingRect(tapete)
    area_tap      = cv2.contourArea(tapete)

    margem = max(tw, th_t)
    x1 = max(0, tx - 10)
    x2 = min(w, tx + tw + 10)
    y2 = min(h, ty + th_t // 4)
    y1 = max(0, ty - margem)

    roi_hsv   = hsv[y1:y2, x1:x2]
    mask_srv  = cv2.inRange(roi_hsv, _servo_hsv_lo, _servo_hsv_hi)
    mask_srv  = cv2.morphologyEx(mask_srv, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts_s, _ = cv2.findContours(mask_srv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    n_servo   = sum(1 for c in cnts_s
                    if _SERVO_BLOB_MIN <= cv2.contourArea(c) <= _SERVO_BLOB_MAX)

    mask_srv_full = np.zeros((h, w), np.uint8)
    mask_srv_full[y1:y2, x1:x2] = mask_srv

    return {
        "bbox":        (x1, y1, x2, y2),
        "tapete_bbox": (tx, ty, tw, th_t),
        "score":       area_tap / 1000.0 + n_servo * 5.0,
        "n_servo":     n_servo,
        "masks":       {"tapete": mask_tap, "servo": mask_srv_full},
    }


def _anotar_frame(frame: np.ndarray, r: dict) -> np.ndarray:
    out = frame.copy()
    x1, y1, x2, y2 = r["bbox"]
    tx, ty, tw, th_t = r["tapete_bbox"]
    cor = (0, 255, 80)
    L   = 22

    cv2.rectangle(out, (tx, ty), (tx + tw, ty + th_t), (0, 165, 255), 1)
    cv2.putText(out, "tapete", (tx + 4, ty + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 165, 255), 1)

    for px, py, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
        cv2.line(out, (px, py), (px + dx*L, py), cor, 3)
        cv2.line(out, (px, py), (px, py + dy*L), cor, 3)

    lbl = f"Rupert  servos:{r['n_servo']}  score:{r['score']:.0f}"
    (tw_l, th_l), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(out, (x1, y1 - th_l - 8), (x1 + tw_l + 6, y1), (0, 70, 0), -1)
    cv2.putText(out, lbl, (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 255, 180), 1)
    return out


@mcp.tool()
def detectar_posicao_rupert(
    camera_index: int = 0, qualidade: int = 80
) -> list[mcp_types.TextContent | mcp_types.ImageContent]:
    """Captura um frame e detecta a posição do Rupert usando o tapete azul como âncora.

    Pipeline:
      1. Detecta o tapete azul-esverdeado por HSV
      2. Projeta o bounding-box do Rupert acima do tapete
      3. Confirma com blobs dos servos SG90 azuis na ROI

    Retorna a foto anotada (bounding-box, tapete, score) + dados estruturados.
    Se não encontrar o tapete, retorna foto crua com aviso — use calibrar_deteccao()
    para ver as máscaras de cor e ajustar os limiares com ajustar_hsv_tapete().

    Args:
        camera_index: índice da câmera (0 = padrão)
        qualidade: qualidade JPEG 1-100
    """
    try:
        cam = _abrir_camera(camera_index)
        for _ in range(3):
            cam.read()
        ok, frame = cam.read()
        if not ok:
            return [mcp_types.TextContent(type="text", text="Erro: não foi possível capturar frame")]
        with _lock:
            global _ultimo_frame
            _ultimo_frame = frame.copy()

        r = _detectar_rupert(frame)
        ts = datetime.now().strftime("%H:%M:%S")

        if r is None:
            info = (
                f"[{ts}] Rupert NÃO detectado — tapete azul não encontrado na cena. "
                f"Limiares atuais: tapete H[{_tapete_hsv_lo[0]}-{_tapete_hsv_hi[0]}] "
                f"S[{_tapete_hsv_lo[1]}-{_tapete_hsv_hi[1]}] V[{_tapete_hsv_lo[2]}-{_tapete_hsv_hi[2]}]. "
                f"Use calibrar_deteccao() para ver as máscaras ou ajustar_hsv_tapete() para ajustar."
            )
            return [
                mcp_types.TextContent(type="text", text=info),
                mcp_types.ImageContent(type="image", data=_frame_para_base64(frame, qualidade), mimeType="image/jpeg"),
            ]

        x1, y1, x2, y2 = r["bbox"]
        info = (
            f"[{ts}] Rupert DETECTADO | "
            f"bbox: ({x1},{y1})→({x2},{y2}) | "
            f"score: {r['score']:.0f} | "
            f"servos visíveis: {r['n_servo']} | "
            f"tapete: {r['tapete_bbox']}"
        )
        anotado = _anotar_frame(frame, r)
        return [
            mcp_types.TextContent(type="text", text=info),
            mcp_types.ImageContent(type="image", data=_frame_para_base64(anotado, qualidade), mimeType="image/jpeg"),
        ]
    except Exception as e:
        return [mcp_types.TextContent(type="text", text=f"Erro na detecção: {e}")]


@mcp.tool()
def calibrar_deteccao(
    camera_index: int = 0,
) -> list[mcp_types.TextContent | mcp_types.ImageContent]:
    """Captura um frame e mostra as máscaras de cor usadas na detecção.

    Retorna dois painéis lado a lado:
      - Esquerda: máscara do tapete azul (laranja = detectado)
      - Direita:  máscara dos servos SG90 (azul = detectado)

    Use para diagnosticar por que o Rupert não está sendo detectado e
    para calibrar os limiares HSV com ajustar_hsv_tapete().

    Args:
        camera_index: índice da câmera (0 = padrão)
    """
    try:
        cam = _abrir_camera(camera_index)
        for _ in range(3):
            cam.read()
        ok, frame = cam.read()
        if not ok:
            return [mcp_types.TextContent(type="text", text="Erro: não foi possível capturar frame")]

        r = _detectar_rupert(frame)
        h, w = frame.shape[:2]

        def _colorir(mask: np.ndarray, cor_bgr: tuple, titulo: str) -> np.ndarray:
            img = np.zeros((h, w, 3), np.uint8)
            img[mask > 0] = cor_bgr
            # mostra contorno no frame original levemente
            frame_escuro = (frame * 0.3).astype(np.uint8)
            img = cv2.addWeighted(img, 0.7, frame_escuro, 0.3, 0)
            cv2.putText(img, titulo, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
            return img

        vazio = np.zeros((h, w), np.uint8)
        masks = r["masks"] if r else {"tapete": vazio, "servo": vazio}

        vis_tap = _colorir(masks["tapete"], (0, 165, 255), "tapete (ancora)")
        vis_srv = _colorir(masks["servo"],  (255, 80,  20), "servos SG90")
        painel  = np.hstack([vis_tap, vis_srv])

        encontrou = "DETECTADO" if r else "NÃO DETECTADO"
        n_servo   = r["n_servo"] if r else 0
        info = (
            f"Calibração | Rupert: {encontrou} | servos visíveis: {n_servo} | "
            f"Tapete HSV H[{_tapete_hsv_lo[0]}-{_tapete_hsv_hi[0]}] "
            f"S[{_tapete_hsv_lo[1]}-{_tapete_hsv_hi[1]}] "
            f"V[{_tapete_hsv_lo[2]}-{_tapete_hsv_hi[2]}] | "
            f"Use ajustar_hsv_tapete() para modificar os limiares."
        )
        return [
            mcp_types.TextContent(type="text", text=info),
            mcp_types.ImageContent(type="image", data=_frame_para_base64(painel), mimeType="image/jpeg"),
        ]
    except Exception as e:
        return [mcp_types.TextContent(type="text", text=f"Erro na calibração: {e}")]


@mcp.tool()
def ajustar_hsv_tapete(
    h_lo: int, s_lo: int, v_lo: int,
    h_hi: int, s_hi: int, v_hi: int,
) -> str:
    """Ajusta os limiares HSV do tapete azul em runtime (sem reiniciar o MCP).

    Use após ver as máscaras com calibrar_deteccao() e identificar que o tapete
    não está sendo capturado corretamente.

    Referência HSV no OpenCV: H=0-179, S=0-255, V=0-255
    Tapete azul-esverdeado típico: H≈85-115, S≈50-255, V≈30-200

    Args:
        h_lo, s_lo, v_lo: limite inferior (Hue, Saturation, Value)
        h_hi, s_hi, v_hi: limite superior
    """
    global _tapete_hsv_lo, _tapete_hsv_hi
    _tapete_hsv_lo = np.array([h_lo, s_lo, v_lo])
    _tapete_hsv_hi = np.array([h_hi, s_hi, v_hi])
    return (
        f"Limiares HSV do tapete atualizados: "
        f"LO=[{h_lo},{s_lo},{v_lo}] HI=[{h_hi},{s_hi},{v_hi}]. "
        f"Chame calibrar_deteccao() para verificar o resultado."
    )


@mcp.tool()
def status_camera() -> dict:
    """Retorna o status atual da câmera e do monitoramento.

    Returns:
        dict com informações de câmera aberta, monitoramento ativo,
        total de frames, e movimento médio detectado.
    """
    return {
        "camera_aberta": _camera is not None and _camera.isOpened(),
        "monitorando": _monitorando,
        "total_frames_capturados": _total_frames,
        "movimento_medio_pct": (
            round(sum(_historico_movimento) / len(_historico_movimento), 2)
            if _historico_movimento
            else None
        ),
        "ultimo_movimento_pct": (
            _historico_movimento[-1] if _historico_movimento else None
        ),
    }


# ─── Inicialização ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Rupert Vision MCP Server iniciando...", flush=True, file=sys.stderr)
    print(
        "Tools disponíveis: capturar_frame, iniciar_monitoramento, "
        "parar_monitoramento, obter_frame_atual, aguardar_movimento_parar, status_camera",
        flush=True,
        file=sys.stderr,
    )
    mcp.run()
