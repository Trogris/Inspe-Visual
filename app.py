import streamlit as st
st.set_page_config(page_title="Analisador de Vídeo Técnico", layout="wide")

# =========================
# Imports
# =========================
import os
import io
import base64
import tempfile
from datetime import datetime

import cv2
import numpy as np
from PIL import Image

# =========================
# Performance/estabilidade
# =========================
try:
    cv2.setNumThreads(2)  # 1 ou 2 ajuda em CPU compartilhada
except Exception:
    pass

# =========================
# Parâmetros fáceis de ajustar
# =========================
NUM_FRAMES   = 10     # mantém 10 frames
TARGET_WIDTH = 640    # redimensionamento na extração
GRID_COLS    = 5      # nº de colunas da grade
PER_PAGE     = 12     # frames por página
THUMB_WIDTH  = 160    # miniatura padrão (metade do tamanho anterior)
VIDEO_COLS   = [1, 1] # player ocupa ~50% da largura (usa a 1ª coluna)

# =========================
# Banner de build (opcional)
# =========================
st.sidebar.success("BUILD: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
st.sidebar.caption("Streamlit: " + st.__version__)

# =========================
# Chaves e estado
# =========================
K_UPLOAD = "upload_video_v1"
K_TECNICO = "input_tecnico_v1"
K_SERIE = "input_serie_v1"
K_STATE = "state_video_meta_v1"
K_PAGE = "pagination_page_v1"

if K_STATE not in st.session_state:
    st.session_state[K_STATE] = {
        "filename": None,
        "temp_video_path": None,
        "duration": 0.0,
        "num_frames": 0,
        "frames": [],  # [{png_bytes, timestamp, frame_number}]
        "timestamp_run": None,
        "tecnico": "",
        "serie": "",
    }
if K_PAGE not in st.session_state:
    st.session_state[K_PAGE] = 1

# =========================
# Utilidades
# =========================
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm"}

def allowed_file(name: str) -> bool:
    if not name:
        return False
    ext = os.path.splitext(name)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def _frame_to_np(fr):
    """
    Converte png_bytes/jpg_bytes/base64/PIL/ndarray -> NumPy RGB uint8 (H,W,3).
    Evita TypeError no st.image por tipos/modes inesperados.
    """
    data = fr.get("jpg_bytes") or fr.get("png_bytes") or fr.get("image")
    if data is None:
        return None

    # base64 -> bytes
    if isinstance(data, str):
        try:
            data = base64.b64decode(data)
        except Exception:
            return None

    # memoryview/bytearray -> bytes
    if isinstance(data, (memoryview, bytearray)):
        data = bytes(data)

    # bytes -> PIL
    if isinstance(data, (bytes,)):
        try:
            img = Image.open(io.BytesIO(data))
            img.load()  # materializa
        except Exception:
            return None
    elif isinstance(data, Image.Image):
        img = data
    elif isinstance(data, np.ndarray):
        arr = data
        # normaliza ndarray para RGB uint8
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        if arr.ndim != 3 or arr.shape[2] not in (3, 4):
            return None
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        if arr.dtype != np.uint8:
            arr = arr.astype(np.uint8, copy=False)
        return np.ascontiguousarray(arr)
    else:
        return None

    # PIL -> RGB ndarray uint8
    if img.mode != "RGB":
        img = img.convert("RGB")
    arr = np.asarray(img)
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8, copy=False)
    if arr.ndim != 3 or arr.shape[2] != 3:
        return None
    return np.ascontiguousarray(arr)

def _ensure_rgb_uint8(arr: np.ndarray) -> np.ndarray:
    """Garante HxWx3, dtype=uint8, memória contígua."""
    if arr is None or not isinstance(arr, np.ndarray):
        return None
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        return None
    if arr.shape[2] == 4:
        arr = arr[:, :, :3]
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8, copy=False)
    return np.ascontiguousarray(arr)

def _safe_show_image(fr, width_px: int, fallback_caption: str):
    """Mostra o frame com fallback para bytes PNG caso st.image rejeite o array."""
    arr = _frame_to_np(fr)
    arr = _ensure_rgb_uint8(arr)
    if arr is None or arr.size == 0:
        st.warning(f"Não foi possível mostrar o {fallback_caption}")
        return
    w = int(max(1, width_px))
    try:
        st.image(arr, caption=fallback_caption, width=w, use_container_width=False)
    except Exception:
        try:
            im = Image.fromarray(arr)
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            st.image(buf.getvalue(), caption=fallback_caption, width=w, use_container_width=False)
        except Exception:
            st.warning(f"Falha ao renderizar {fallback_caption}.")

def extract_frames_from_video(video_path: str, num_frames: int = NUM_FRAMES, target_width: int = TARGET_WIDTH):
    """Extrai N frames distribuídos ao longo do vídeo (mantendo PNG) com pequenos reforços de robustez."""
    frames = []
    duration = 0.0

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], 0.0

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    total_frames = int(cv2.VideoCapture(video_path).get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    # usa o handle atual para evitar novo open:
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if fps <= 0 or total_frames <= 0:
        cap.release()
        return [], 0.0

    duration = total_frames / fps
    indexes = np.linspace(0, total_frames - 1, num=num_frames, dtype=int)

    for i, idx in enumerate(indexes):
        # Tenta por frame; se falhar, fallback por tempo (MSEC)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok or frame is None:
            t_sec = idx / fps if fps > 0 else 0
            cap.set(cv2.CAP_PROP_POS_MSEC, float(t_sec * 1000.0))
            ok, frame = cap.read()
        if not ok or frame is None:
            continue

        # BGR -> RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Resize proporcional
        h, w, _ = frame_rgb.shape
        if w > target_width:
            new_w = target_width
            new_h = int(h * (target_width / w))
            frame_rgb = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # PNG bytes
        pil_img = Image.fromarray(frame_rgb)
        buff = io.BytesIO()
        pil_img.save(buff, format="PNG", optimize=True)
        png_bytes = buff.getvalue()

        timestamp = round(idx / fps, 2)
        frames.append({
            "png_bytes": png_bytes,
            "timestamp": timestamp,
            "frame_number": int(i + 1),
        })

    cap.release()
    return frames, duration

def build_report_text(state: dict) -> str:
    """Gera o texto do relatório a partir do estado atual."""
    lines = []
    lines.append("RELATÓRIO DE ANÁLISE DE VÍDEO TÉCNICO")
    lines.append("=" * 35)
    lines.append(f"Data/Hora: {state.get('timestamp_run', '')}")
    lines.append(f"Técnico: {state.get('tecnico', '')}")
    lines.append(f"Nº de Série: {state.get('serie', '')}")
    lines.append(f"Arquivo: {state.get('filename', '')}")
    lines.append(f"Duração (s): {round(state.get('duration', 0.0), 2)}")
    lines.append("")
    lines.append("FRAMES EXTRAÍDOS:")
    for f in state.get("frames", []):
        lines.append(f"- Frame {f['frame_number']:02d} | t={f['timestamp']}s")
    return "\n".join(lines)

# =========================
# Layout ESTÁVEL (tabs fixas)
# =========================
tabs = st.tabs(["Upload", "Pré-visualização", "Frames", "Relatório"])

# ---------- TAB 1: Upload ----------
with tabs[0]:
    st.markdown("### 1) Envie o vídeo e os dados")
    col1, col2 = st.columns(2)
    with col1:
        tecnico = st.text_input("Nome do Técnico", key=K_TECNICO)
    with col2:
        serie = st.text_input("Número de Série do Equipamento", key=K_SERIE)

    video_file = st.file_uploader(
        "Selecionar Vídeo (até 200MB)",
        type=[e.strip(".") for e in ALLOWED_EXTENSIONS],
        key=K_UPLOAD
    )

    processar = st.button("📤 Enviar e Analisar", use_container_width=True, key="btn_enviar_v1")
    if processar:
        if not video_file or not video_file.name:
            st.error("Nenhum arquivo enviado.")
        elif not allowed_file(video_file.name):
            st.error("Formato não suportado.")
        else:
            tmpdir = tempfile.mkdtemp(prefix="vid_")
            safe_name = os.path.basename(video_file.name).replace(" ", "_")
            video_path = os.path.join(tmpdir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}")
            with open(video_path, "wb") as f:
                f.write(video_file.read())

            # Aviso de duração recomendada (não bloqueante)
            cap_tmp = cv2.VideoCapture(video_path)
            fps_tmp = cap_tmp.get(cv2.CAP_PROP_FPS) or 0
            total_tmp = int(cap_tmp.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            cap_tmp.release()
            if fps_tmp > 0 and total_tmp > 0:
                dur_tmp = total_tmp / fps_tmp
                if not (20 <= dur_tmp <= 40):
                    st.info(f"Atenção: vídeo com {dur_tmp:.2f}s (recomendado entre 20 e 40s).")

            with st.spinner("Processando vídeo e extraindo frames..."):
                frames, duration = extract_frames_from_video(
                    video_path, num_frames=NUM_FRAMES, target_width=TARGET_WIDTH
                )

            if not frames:
                st.error("Falha ao extrair frames. Verifique o codec do vídeo.")
            else:
                st.session_state[K_STATE] = {
                    "filename": safe_name,
                    "temp_video_path": video_path,
                    "duration": float(duration),
                    "num_frames": len(frames),
                    "frames": frames,
                    "timestamp_run": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "tecnico": tecnico,
                    "serie": serie,
                }
                st.session_state[K_PAGE] = 1
                st.success("Análise concluída! Vá para as abas de Pré-visualização e Frames.")

# ---------- TAB 2: Pré-visualização ----------
with tabs[1]:
    st.markdown("### 2) Pré-visualização do vídeo (50% da largura)")
    state = st.session_state[K_STATE]
    if state["temp_video_path"] and os.path.exists(state["temp_video_path"]):
        cols = st.columns(VIDEO_COLS)  # duas colunas → 50%
        with cols[0]:  # usa só a primeira coluna
            st.video(state["temp_video_path"], format="video/mp4", start_time=0)
            st.caption(f"Arquivo: {state['filename']} — Duração: {round(state['duration'], 2)}s")
    else:
        st.info("Envie um vídeo na aba **Upload**.")

# ---------- TAB 3: Frames ----------
with tabs[2]:
    st.markdown("### 3) Frames extraídos (miniaturas 50%)")
    state = st.session_state[K_STATE]
    frames = state["frames"]
    if frames:
        # Header com paginação
        top = st.container()
        with top:
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                st.write(f"Total de frames: **{len(frames)}**")
            with c2:
                st.write(f"Duração: **{round(state['duration'], 2)}s**")
            with c3:
                total_pages = max(1, (len(frames) + PER_PAGE - 1) // PER_PAGE)
                current_page = st.session_state.get(K_PAGE, 1)
                st.session_state[K_PAGE] = st.number_input(
                    "Página", min_value=1, max_value=total_pages,
                    value=min(current_page, total_pages),
                    step=1, key="page_selector_v1"
                )

        thumb_w = st.slider("Tamanho das miniaturas (px)", 120, 320, THUMB_WIDTH, 10, key="thumb_w_v1")

        start = (st.session_state[K_PAGE] - 1) * PER_PAGE
        end = start + PER_PAGE
        subset = frames[start:end]

        cols = st.columns(GRID_COLS)  # grade fixa
        for i, fr in enumerate(subset):
            with cols[i % GRID_COLS]:
                caption = f"Frame {int(fr.get('frame_number', i+1))} — t={str(fr.get('timestamp','?'))}s"
                _safe_show_image(fr, int(thumb_w), caption)
    else:
        st.info("Nenhum frame disponível. Faça o upload na aba **Upload**.")

# ---------- TAB 4: Relatório ----------
with tabs[3]:
    st.markdown("### 4) Relatório")
    state = st.session_state[K_STATE]
    if state["frames"]:
        report = build_report_text(state)
        st.text_area("Prévia do relatório", report, height=260, key="report_preview_v1")
        st.download_button(
            "📥 Baixar relatório (.txt)",
            data=report.encode("utf-8"),
            file_name="relatorio_analise_video_tecnico.txt",
            mime="text/plain",
            key="dl_report_v1"
        )
    else:
        st.info("Gere uma análise primeiro na aba **Upload**.")
