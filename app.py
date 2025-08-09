import datetime as _dt
st.sidebar.success("BUILD: " + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
st.sidebar.caption("Streamlit: " + st.__version__)

import streamlit as st
st.set_page_config(page_title="Analisador de Vídeo Técnico", layout="wide")

import os
import io
import tempfile
from datetime import datetime

import cv2
import numpy as np
from PIL import Image

# ---------- Performance OpenCV ----------
# Limita threads para reduzir overhead em CPU compartilhada (Cloud)
try:
    cv2.setNumThreads(2)
except Exception:
    pass

# ---------- Constantes / Chaves ----------
K_UPLOAD = "upload_video_v1"
K_TECNICO = "input_tecnico_v1"
K_SERIE = "input_serie_v1"
K_STATE = "state_video_meta_v1"
K_PAGE = "pagination_page_v1"

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm"}
MIN_SEC = 20.0
MAX_SEC = 40.0
N_FRAMES = 10             # manter 10 frames (pedido do usuário)
TARGET_WIDTH = 480        # largura alvo para acelerar processamento
JPEG_QUALITY = 70         # 60–80 é um bom intervalo

# ---------- Estado seguro ----------
def ensure_state():
    if K_STATE not in st.session_state:
        st.session_state[K_STATE] = {
            "filename": None,
            "temp_video_path": None,
            "duration": 0.0,
            "num_frames": 0,
            "frames": [],  # [{jpg_bytes, timestamp, frame_number}]
            "timestamp_run": None,
            "tecnico": "",
            "serie": "",
        }
    if K_PAGE not in st.session_state:
        st.session_state[K_PAGE] = 1

ensure_state()

# ---------- Utils ----------
def allowed_file(name: str) -> bool:
    if not name:
        return False
    ext = os.path.splitext(name)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def extract_frames_from_video(
    video_path: str,
    num_frames: int = N_FRAMES,
    target_width: int = TARGET_WIDTH,
    jpeg_quality: int = JPEG_QUALITY
):
    """
    Extrai N frames distribuídos ao longo do vídeo.
    - Busca preferencial por tempo (MSEC), com fallback por índice de frame
    - Redimensiona mantendo proporção
    - Codifica em JPEG para velocidade/leveza
    """
    frames = []
    duration = 0.0

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], 0.0

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0 or total_frames <= 0:
        cap.release()
        return [], 0.0

    duration = total_frames / fps

    # timestamps alvo entre 0 e duration
    ts = np.linspace(0, max(duration - 1e-3, 0), num=num_frames)

    for i, t in enumerate(ts):
        # tentar pular por tempo (milissegundos)
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t * 1000.0))
        ok, frame = cap.read()
        if not ok or frame is None:
            # fallback por frame index
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(min(round(t * fps), total_frames - 1)))
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

        # Encode JPEG (mais rápido/leve)
        pil_img = Image.fromarray(frame_rgb)
        buff = io.BytesIO()
        pil_img.save(buff, format="JPEG", quality=jpeg_quality, optimize=True)
        jpg_bytes = buff.getvalue()

        frames.append({
            "jpg_bytes": jpg_bytes,
            "timestamp": round(t, 2),
            "frame_number": int(i + 1),
        })

    cap.release()
    return frames, duration

def build_report_text(state: dict) -> str:
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

# ---------- Prova de build (opcional) ----------
st.sidebar.success("BUILD: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
st.sidebar.caption("Streamlit: " + st.__version__)

# ---------- Layout estável ----------
tabs = st.tabs(["Upload", "Pré-visualização", "Frames", "Relatório"])

# ===== TAB 1: Upload =====
with tabs[0]:
    st.markdown("### 1) Envie o vídeo e os dados (entre 20 e 40 segundos)")

    col1, col2 = st.columns(2)
    with col1:
        tecnico = st.text_input("Nome do Técnico", key=K_TECNICO)
    with col2:
        serie = st.text_input("Número de Série do Equipamento", key=K_SERIE)

    video_file = st.file_uploader(
        "Selecionar Vídeo (20–40s, até 200MB)",
        type=[e.strip(".") for e in ALLOWED_EXTENSIONS],
        key=K_UPLOAD
    )

    processar = st.button("📤 Enviar e Analisar", use_container_width=True, key="btn_enviar_v1")
    if processar:
        if not video_file or not video_file.name:
            st.error("Nenhum arquivo enviado.")
        elif not allowed_file(video_file.name):
            st.error("Formato não suportado. Envie um vídeo em: " + ", ".join(sorted(ALLOWED_EXTENSIONS)))
        else:
            # Salva vídeo em arquivo temporário
            tmpdir = tempfile.mkdtemp(prefix="vid_")
            safe_name = os.path.basename(video_file.name).replace(" ", "_")
            video_path = os.path.join(tmpdir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}")
            with open(video_path, "wb") as f:
                f.write(video_file.read())

            # Primeiro, calcule duração para validar intervalo 20–40s
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            cap.release()
            if fps <= 0 or total_frames <= 0:
                st.error("Não foi possível ler o vídeo. Verifique o codec/arquivo.")
            else:
                duration_check = total_frames / fps
                if duration_check < MIN_SEC or duration_check > MAX_SEC:
                    st.error(f"O vídeo deve ter entre {int(MIN_SEC)} e {int(MAX_SEC)} segundos. "
                             f"Duração detectada: {round(duration_check,2)}s.")
                else:
                    # Extração de frames (10 frames)
                    frames, duration = extract_frames_from_video(
                        video_path,
                        num_frames=N_FRAMES,
                        target_width=TARGET_WIDTH,
                        jpeg_quality=JPEG_QUALITY
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

# ===== TAB 2: Pré-visualização =====
with tabs[1]:
    st.markdown("### 2) Pré-visualização do vídeo")
    state = st.session_state[K_STATE]
    if state["temp_video_path"] and os.path.exists(state["temp_video_path"]):
        st.video(state["temp_video_path"])  # componente nativo estável
        st.caption(f"Arquivo: {state['filename']} — Duração: {round(state['duration'], 2)}s")
    else:
        st.info("Envie um vídeo na aba **Upload**.")

# ===== TAB 3: Frames =====
with tabs[2]:
    st.markdown("### 3) Frames extraídos (10 frames)")
    state = st.session_state[K_STATE]
    frames = state["frames"]
    if frames:
        # Paginação estável (4 colunas fixas)
        per_page = 8
        total = len(frames)
        pages = max(1, (total + per_page - 1) // per_page)

        top = st.container()
        with top:
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                st.write(f"Total de frames: **{total}**")
            with c2:
                st.write(f"Duração: **{round(state['duration'], 2)}s**")
            with c3:
                current_page = st.session_state.get(K_PAGE, 1)
                st.session_state[K_PAGE] = st.number_input(
                    "Página", min_value=1, max_value=pages,
                    value=min(current_page, pages),
                    step=1, key="page_selector_v1"
                )

        start = (st.session_state[K_PAGE] - 1) * per_page
        end = start + per_page
        subset = frames[start:end]

        cols = st.columns(4)  # fixo
        for i, fr in enumerate(subset):
            with cols[i % 4]:
                st.image(fr["jpg_bytes"],
                         caption=f"Frame {fr['frame_number']} — t={fr['timestamp']}s",
                         use_container_width=True)
    else:
        st.info("Nenhum frame disponível. Faça o upload na aba **Upload**.")

# ===== TAB 4: Relatório =====
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
