#!/usr/bin/env python3
# teste_visao_rupert.py
# Detecta Rupert usando o tapete azul como âncora de posição.
# O robô está sempre em cima do tapete — detecta o tapete, projeta o Rupert acima dele.
#
# Q=sair | S=screenshot | O=YOLO | A=ArUco | M=máscara mov | C=debug

import time
import cv2
import numpy as np

# ── Câmera / geral ─────────────────────────────────────────────────────────────
CAMERA_INDEX     = 0
LIMIAR_DIFF      = 15
LIMIAR_MOV_PCT   = 2.0
CONF_YOLO        = 0.45
AREA_MIN_CONTOUR = 800

# ── Tapete azul (âncora principal) ─────────────────────────────────────────────
# Tapete de corte azul-esverdeado onde o Rupert fica posicionado
TAPETE_HSV_LO   = np.array([ 78,  50,  30])
TAPETE_HSV_HI   = np.array([115, 255, 200])
TAPETE_AREA_MIN = 4000    # px² — rejeita reflexos pequenos

# ── Servo SG90 — confirmação secundária, buscado só na ROI do tapete ──────────
SERVO_HSV_LO   = np.array([ 95,  70,  50])
SERVO_HSV_HI   = np.array([140, 255, 220])
SERVO_BLOB_MIN = 40
SERVO_BLOB_MAX = 1800

# ── YOLO ───────────────────────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    _modelo = YOLO("yolov8n.pt")
    YOLO_OK = True
    print("[YOLO] YOLOv8n pronto.")
except Exception as e:
    YOLO_OK, _modelo = False, None
    print(f"[YOLO] Indisponível: {e}")

# ── ArUco ──────────────────────────────────────────────────────────────────────
_aruco_det = cv2.aruco.ArucoDetector(
    cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
    cv2.aruco.DetectorParameters(),
)


# ══════════════════════════════════════════════════════════════════════════════
# Detecção do Rupert
# ══════════════════════════════════════════════════════════════════════════════

def detectar_rupert(frame: np.ndarray) -> dict | None:
    """
    1. Detecta o tapete azul (grande blob azul-esverdeado).
    2. Projeta o bbox do Rupert acima do tapete.
    3. Confirma com servos SG90 azuis dentro da ROI esperada.
    """
    h, w = frame.shape[:2]
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # ── tapete ───────────────────────────────────────────────────────────
    mask_tap = cv2.inRange(hsv, TAPETE_HSV_LO, TAPETE_HSV_HI)
    mask_tap = cv2.morphologyEx(mask_tap, cv2.MORPH_OPEN,  np.ones((5,  5),  np.uint8))
    mask_tap = cv2.morphologyEx(mask_tap, cv2.MORPH_CLOSE, np.ones((20, 20), np.uint8))

    cnts, _ = cv2.findContours(mask_tap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts    = [c for c in cnts if cv2.contourArea(c) >= TAPETE_AREA_MIN]
    if not cnts:
        return None

    tapete        = max(cnts, key=cv2.contourArea)
    tx, ty, tw, th_t = cv2.boundingRect(tapete)
    area_tap      = cv2.contourArea(tapete)

    # ── bbox do Rupert acima do tapete ───────────────────────────────────
    margem = max(tw, th_t)
    x1 = max(0, tx - 10)
    x2 = min(w, tx + tw + 10)
    y2 = min(h, ty + th_t // 4)
    y1 = max(0, ty - margem)

    # ── servos na ROI ─────────────────────────────────────────────────────
    roi_hsv    = hsv[y1:y2, x1:x2]
    mask_srv_r = cv2.inRange(roi_hsv, SERVO_HSV_LO, SERVO_HSV_HI)
    mask_srv_r = cv2.morphologyEx(mask_srv_r, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts_s, _  = cv2.findContours(mask_srv_r, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    n_servo    = sum(1 for c in cnts_s
                     if SERVO_BLOB_MIN <= cv2.contourArea(c) <= SERVO_BLOB_MAX)

    mask_srv = np.zeros((h, w), np.uint8)
    mask_srv[y1:y2, x1:x2] = mask_srv_r

    return {
        "bbox":        (x1, y1, x2, y2),
        "tapete_bbox": (tx, ty, tw, th_t),
        "score":       area_tap / 1000.0 + n_servo * 5.0,
        "n_servo":     n_servo,
        "masks":       {"tapete": mask_tap, "servo": mask_srv},
    }


def desenhar_rupert(frame: np.ndarray, r: dict):
    x1, y1, x2, y2 = r["bbox"]
    cor = (0, 255, 80)
    L   = 22

    # contorno do tapete em laranja
    tx, ty, tw, th_t = r["tapete_bbox"]
    cv2.rectangle(frame, (tx, ty), (tx + tw, ty + th_t), (0, 165, 255), 1)
    cv2.putText(frame, "tapete", (tx + 4, ty + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 165, 255), 1)

    # cantos em L do bbox do Rupert
    for px, py, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
        cv2.line(frame, (px, py), (px + dx*L, py), cor, 3)
        cv2.line(frame, (px, py), (px, py + dy*L), cor, 3)

    lbl = f"Rupert  servos:{r['n_servo']}  score:{r['score']:.0f}"
    (tw_l, th_l), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(frame, (x1, y1 - th_l - 8), (x1 + tw_l + 6, y1), (0, 70, 0), -1)
    cv2.putText(frame, lbl, (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 255, 180), 1)


def painel_debug(frame: np.ndarray, r: dict | None) -> np.ndarray:
    h, w  = frame.shape[:2]
    vazio = np.zeros((h, w), np.uint8)

    def _vis(mask, cor_bgr, titulo):
        img = np.zeros((h, w, 3), np.uint8)
        img[mask > 0] = cor_bgr
        cv2.putText(img, titulo, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
        return img

    masks   = r["masks"] if r else {"tapete": vazio, "servo": vazio}
    vis_tap = _vis(masks["tapete"], (0, 180, 255), "tapete azul (ancora)")
    vis_srv = _vis(masks["servo"],  (200, 80,   0), "servos na ROI")

    painel = np.hstack([vis_tap, vis_srv])
    esc    = h / painel.shape[0]
    return cv2.resize(painel, (int(painel.shape[1] * esc), h))


# ══════════════════════════════════════════════════════════════════════════════
# Detecções auxiliares
# ══════════════════════════════════════════════════════════════════════════════

def detectar_yolo(frame: np.ndarray) -> list[dict]:
    if not YOLO_OK:
        return []
    results = _modelo(frame, conf=CONF_YOLO, verbose=False)[0]
    return [
        {"nome": results.names[int(b.cls[0])],
         "conf": float(b.conf[0]),
         "bbox": tuple(map(int, b.xyxy[0]))}
        for b in results.boxes
    ]


def detectar_aruco(frame: np.ndarray) -> list[dict]:
    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _aruco_det.detectMarkers(cinza)
    if ids is None:
        return []
    return [{"id":      int(ids[i][0]),
             "corners": corners[i][0].astype(int),
             "centro":  corners[i][0].mean(axis=0).astype(int)}
            for i in range(len(ids))]


def calcular_movimento(ant: np.ndarray, atual: np.ndarray) -> tuple[float, np.ndarray]:
    diff = cv2.absdiff(cv2.cvtColor(ant,   cv2.COLOR_BGR2GRAY),
                       cv2.cvtColor(atual, cv2.COLOR_BGR2GRAY))
    _, mask = cv2.threshold(diff, LIMIAR_DIFF, 255, cv2.THRESH_BINARY)
    mask = cv2.dilate(mask, None, iterations=2)
    pct  = 100.0 * np.sum(mask > 0) / mask.size
    bgr  = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    bgr[:, :, 0] = 0
    bgr[:, :, 1] = 0
    return pct, bgr


def contornos_movimento(mask_bgr: np.ndarray) -> list[tuple]:
    cinza = cv2.cvtColor(mask_bgr, cv2.COLOR_BGR2GRAY)
    cnts, _ = cv2.findContours(cinza, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) >= AREA_MIN_CONTOUR]


# ── Desenho ────────────────────────────────────────────────────────────────────
def _cor_classe(n):
    h = hash(n) & 0xFFFFFF
    return (h & 0xFF, (h >> 8) & 0xFF, (h >> 16) & 0xFF)


def _label(frame, txt, x, y, cor):
    (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(frame, (x, y - th - 6), (x + tw + 4, y), cor, -1)
    cv2.putText(frame, txt, (x + 2, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def desenhar_yolo(frame, dets):
    for d in dets:
        x1, y1, x2, y2 = d["bbox"]
        cor = _cor_classe(d["nome"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), cor, 2)
        _label(frame, f"{d['nome']} {d['conf']:.0%}", x1, y1, cor)


def desenhar_aruco(frame, marcadores):
    for m in marcadores:
        cv2.polylines(frame, [m["corners"]], True, (0, 255, 255), 2)
        cx, cy = m["centro"]
        cv2.putText(frame, f"ArUco #{m['id']}", (cx + 8, cy - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)


def desenhar_mov(frame, bboxes):
    for x, y, w, h in bboxes:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 165, 255), 1)
        cv2.putText(frame, "mov", (x, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)


def desenhar_hud(frame, pct_mov, fps, em_mov, n_obj, n_aruco, rupert):
    h, w = frame.shape[:2]
    cor  = (0, 60, 220) if em_mov else (0, 200, 60)
    ov   = frame.copy()
    cv2.rectangle(ov, (0, 0), (w, 62), (20, 20, 20), -1)
    cv2.addWeighted(ov, 0.6, frame, 0.4, 0, frame)

    cv2.putText(frame, f"FPS:{fps:.0f}  Mov:{pct_mov:.1f}%  Obj:{n_obj}  ArUco:{n_aruco}",
                (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    if rupert:
        r_txt = f"Rupert: ENCONTRADO  tapete+{rupert['n_servo']}servos"
        r_cor = (0, 255, 80)
    else:
        r_txt = "Rupert: tapete nao encontrado"
        r_cor = (80, 80, 80)
    cv2.putText(frame, r_txt, (8, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.52, r_cor, 1)
    cv2.putText(frame, "Q=sair O=YOLO A=ArUco M=mask C=debug S=shot",
                (8, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (140, 140, 140), 1)

    cv2.putText(frame, "MOVIMENTO" if em_mov else "Parado",
                (w - 185, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)
    bw = int(w * min(pct_mov / 20.0, 1.0))
    cv2.rectangle(frame, (0, h - 8), (bw, h), cor, -1)
    cv2.rectangle(frame, (0, h - 8), (w, h), (60, 60, 60), 1)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    cam = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(CAMERA_INDEX)
    if not cam.isOpened():
        print(f"Erro: câmera {CAMERA_INDEX} não acessível.")
        return

    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("=" * 55)
    print("  Rupert Vision — âncora: tapete azul de corte")
    print("  C = debug (tapete + servos)  |  Q = sair")
    print("  Se o tapete não for detectado, pressione C para ver")
    print("  a máscara e ajuste TAPETE_HSV_LO/HI no topo do arquivo")
    print("=" * 55)

    frame_ant = None
    pct_mov   = 0.0
    mask_cor  = None
    t_ant     = time.time()
    fps       = 0.0
    shot_n    = 0
    flags     = {"mascara": True, "yolo": True, "aruco": True, "rupert": True, "debug": False}

    while True:
        ok, frame = cam.read()
        if not ok:
            print("Erro ao ler frame.")
            break

        agora = time.time()
        fps   = 0.9 * fps + 0.1 / max(agora - t_ant, 1e-6)
        t_ant = agora

        if frame_ant is not None:
            pct_mov, mask_cor = calcular_movimento(frame_ant, frame)
        frame_ant = frame.copy()
        em_mov    = pct_mov >= LIMIAR_MOV_PCT

        exibir = frame.copy()

        dets   = detectar_yolo(frame)   if flags["yolo"]   else []
        aruco  = detectar_aruco(frame)  if flags["aruco"]  else []
        rupert = detectar_rupert(frame) if flags["rupert"] else None
        bboxes = (contornos_movimento(mask_cor)
                  if mask_cor is not None and em_mov else [])

        desenhar_mov(exibir, bboxes)
        desenhar_yolo(exibir, dets)
        desenhar_aruco(exibir, aruco)
        if rupert:
            desenhar_rupert(exibir, rupert)
        desenhar_hud(exibir, pct_mov, fps, em_mov, len(dets), len(aruco), rupert)

        paineis = [exibir]
        if flags["mascara"] and mask_cor is not None:
            paineis.append(mask_cor)
        if flags["debug"]:
            paineis.append(painel_debug(frame, rupert))

        cv2.imshow("Rupert Vision", np.hstack(paineis))

        tecla = cv2.waitKey(1) & 0xFF
        if   tecla == ord('q'): break
        elif tecla == ord('s'):
            nome = f"rupert_shot_{shot_n:03d}.jpg"
            cv2.imwrite(nome, np.hstack(paineis))
            print(f"Screenshot: {nome}")
            shot_n += 1
        elif tecla == ord('m'): flags["mascara"] = not flags["mascara"]
        elif tecla == ord('o'): flags["yolo"]    = not flags["yolo"]
        elif tecla == ord('a'): flags["aruco"]   = not flags["aruco"]
        elif tecla == ord('r'): flags["rupert"]  = not flags["rupert"]
        elif tecla == ord('c'):
            flags["debug"] = not flags["debug"]
            print(f"Debug: {'ON' if flags['debug'] else 'OFF'}")

    cam.release()
    cv2.destroyAllWindows()
    print("Encerrado.")


if __name__ == "__main__":
    main()
