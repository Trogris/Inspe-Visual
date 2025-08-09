import streamlit as st
st.set_page_config(page_title="Analisador de Vídeo Técnico", layout="wide")

# ========= Imports =========
import os
import io
import base64
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
import zipfile
import re
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image

# ========= Performance / estabilidade =========
try:
    cv2.setNumThreads(2)  # 1 ou 2 ajuda em CPU compartilhada
except Exception:
    pass

# ========= Parâmetros =========
NUM_FRAMES   = 10     # manter 10 frames
TARGET_WIDTH = 640    # redimensionamento na extração
GRID_COLS    = 5      # nº de colunas na grade
THUMB_WIDTH  = 160    # miniatura padrão
VIDEO_COLS   = [1, 3] # ~25% da largura (altura do player fica menor)
TZ_BR = ZoneInfo("America/Sao_Paulo")

# ========= Banner (opcional) =========
st.sidebar.success("BUILD: " + datetime.now(TZ_BR).strftime("%Y-%m-%d %H:%M:%S"))
st.sidebar.caption("Streamlit: " + st.__version__)

# ========= Estado =========
K_UPLOAD    = "upload_video_v1"
K_TECNICO   = "input_tecnico_v1"
K_SERIE     = "input_serie_v1"
K_CONTRATO  = "input_contrato_v1"
K_STATE     = "state_video_meta_v1"

def _initial_state():
    return {
        "temp_dir": None,          # pasta temporária para limpeza completa
        "filename": None,
        "temp_video_path": None,
        "duration": 0.0,
        "num_frames": 0,
        "frames": [],              # [{arr, png_bytes, timestamp, frame_number, shape, dtype}]
        "timestamp_run": None,
        "tecnico": "",
        "serie": "",
        "contrato": "",
    }

if K_STATE not in st.session_state:
    st.session_state[K_STATE] = _initial_state()

# ========= Utilidades =========
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm"}

def allowed_file(name: str) -> bool:
    if not name:
        return False
    return os.path.splitext(name)[1].lower() in ALLOWED_EXTENSIONS

def _slugify(text: str, fallback: str = "sem_valor") -> str:
    """Transforma texto em pasta segura (sem pontuação problemática/espacos múltiplos)."""
    if not text:
        return fallback
    t = text.strip()
    t = re.sub(r"[^\w\s-]", "_", t, flags=re.UNICODE)  # remove pontuação/acento
    t = re.sub(r"\s+", "_", t)                        # espaços -> _
    t = re.sub(r"_+", "_", t).strip("_.")             # colapsa _
    return t or fallback

def extract_frames_from_video(video_path: str, num_frames: int = NUM_FRAMES, target_width: int = TARGET_WIDTH):
    """
    Extrai N frames ao longo do vídeo.
    Exibição usa SEMPRE 'arr' (NumPy RGB uint8 contíguo).
    'png_bytes' fica apenas para download.
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
    indexes = np.linspace(0, total_frames - 1, num=num_frames, dtype=int)

    for i, idx in enumerate(indexes):
        # Seek por frame -> fallback por tempo
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

        # Arr RGB uint8 contíguo (base para exibição)
        arr = np.ascontiguousarray(frame_rgb, dtype=np.uint8)

        # Bytes PNG (para download)
        buff = io.BytesIO()
        Image.fromarray(arr).save(buff, format="PNG", optimize=True)
        png_bytes = buff.getvalue()

        frames.append({
            "arr": arr,
            "png_bytes": png_bytes,
            "timestamp": round(idx / fps, 2),
            "frame_number": int(i + 1),
            "shape": tuple(arr.shape),     # debug opcional
            "dtype": str(arr.dtype),       # debug opcional
        })

    cap.release()
    return frames, duration

def build_report_text(state: dict) -> str:
    lines = []
    lines.append("RELATÓRIO DE ANÁLISE DE VÍDEO TÉCNICO")
    lines.append("=" * 35)
    lines.append(f"Data/Hora (Brasília): {state.get('timestamp_run', '')}")
    lines.append(f"Técnico: {state.get('tecnico', '')}")
    lines.append(f"Nº de Série: {state.get('serie', '')}")
    lines.append(f"Contrato: {state.get('contrato', '')}")
    lines.append(f"Arquivo: {state.get('filename', '')}")
    lines.append(f"Duração (s): {round(state.get('duration', 0.0), 2)}")
    lines.append("")
    lines.append("FRAMES EXTRAÍDOS:")
    for f in state.get("frames", []):
        lines.append(f"- Frame {f['frame_number']:02d} | t={f['timestamp']}s")
    return "\n".join(lines)

def _safe_show_image(fr, width_px: int, caption: str):
    """Renderiza SEMPRE: arr -> PIL(RGB) -> PNG. Se st.image falhar, usa <img> base64."""
    w = int(max(1, width_px))

    # 1) arr -> PIL RGB
    img = None
    arr = fr.get("arr")
    if isinstance(arr, np.ndarray):
        try:
            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr], axis=-1)
            if arr.ndim >= 3:
                arr = arr[:, :, :3]
            if arr.dtype != np.uint8:
                arr = arr.astype(np.uint8, copy=False)
            img = Image.fromarray(np.ascontiguousarray(arr), mode="RGB")
        except Exception:
            img = None

    # 2) se não tiver arr, usa png_bytes -> PIL RGB
    if img is None:
        png_bytes = fr.get("png_bytes")
        if isinstance(png_bytes, (bytes, bytearray, memoryview)) and len(png_bytes) > 0:
            try:
                tmp = Image.open(io.BytesIO(bytes(png_bytes)))
                img = tmp.convert("RGB")
            except Exception:
                img = None

    if img is None:
        st.warning(f"Falha ao renderizar {caption}.")
        return

    # 3) tenta st.image normalmente (forçando PNG)
    try:
        st.image(img, caption=caption, width=w, use_container_width=False, output_format="PNG")
        return
    except Exception:
        pass

    # 4) Fallback final: <img> base64 (HTML)
    try:
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        html = f"""
        <div style="width:{w}px;text-align:center;">
          <img src="data:image/png;base64,{b64}" width="{w}" />
          <div style="font-size:12px;color:#666;">{caption}</div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    except Exception:
        st.warning(f"Falha ao renderizar {caption} (fallback HTML).")

def build_zip_package(state: dict) -> tuple[bytes, str]:
    """
    Monta um .zip em memória com:
      /<CONTRATO>_<SERIE>/
        relatorio_analise_video_tecnico.txt
        <video_original>
        frames/frame_01.png ... frame_10.png
    """
    serie_slug = _slugify(state.get("serie", ""))
    contrato_slug = _slugify(state.get("contrato", ""))
    folder_slug = f"{contrato_slug}_{serie_slug}".strip("_") or "pacote"
    base_dir = f"{folder_slug}/"

    # Relatório
    report_txt = build_report_text(state).encode("utf-8")

    # Vídeo
    video_path = state.get("temp_video_path")
    video_bytes = None
    video_name = None
    if video_path and os.path.exists(video_path):
        video_name = Path(state.get("filename") or Path(video_path).name).name
        with open(video_path, "rb") as vf:
            video_bytes = vf.read()

    # Frames
    frames = state.get("frames", [])

    # Zip em memória
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # relatório
        zf.writestr(base_dir + "relatorio_analise_video_tecnico.txt", report_txt)

        # vídeo (se disponível)
        if video_bytes is not None and video_name:
            zf.writestr(base_dir + video_name, video_bytes)

        # frames
        for f in frames:
            n = int(f.get("frame_number", 0))
            png = f.get("png_bytes")
            if isinstance(png, (bytes, bytearray, memoryview)) and len(png) > 0:
                zf.writestr(base_dir + f"frames/frame_{n:02d}.png", bytes(png))

    zip_bytes = buf.getvalue()
    zip_filename = f"pacote_{folder_slug}.zip"
    return zip_bytes, zip_filename

def _reset_analysis():
    """Remove a pasta temporária, limpa TODO o session_state e recarrega a página."""
    try:
        state = st.session_state.get(K_STATE, {})
        temp_dir = state.get("temp_dir")
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

    st.session_state.clear()  # limpa widgets e estados

    # Após limpar, o rerun volta à primeira aba (Upload)
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()

# ========= Layout (tabs fixas) =========
tabs = st.tabs(["Upload", "Pré-visualização", "Frames", "Relatório", "Nova análise"])

# --- TAB 1: Upload ---
with tabs[0]:
    st.markdown("### 1) Envie o vídeo e os dados")
    col1, col2, col3 = st.columns(3)
    with col1:
        tecnico = st.text_input("Nome do Técnico", key=K_TECNICO)
    with col2:
        serie = st.text_input("Número de Série do Equipamento", key=K_SERIE)
    with col3:
        contrato = st.text_input("Contrato", key=K_CONTRATO)

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
            # guarda a pasta temp para limpeza posterior
            st.session_state[K_STATE]["temp_dir"] = tmpdir

            video_path = os.path.join(tmpdir, f"{datetime.now(TZ_BR).strftime('%Y%m%d_%H%M%S')}_{safe_name}")
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
                st.session_state[K_STATE].update({
                    "filename": safe_name,
                    "temp_video_path": video_path,
                    "duration": float(duration),
                    "num_frames": len(frames),
                    "frames": frames,
                    "timestamp_run": datetime.now(TZ_BR).strftime("%d/%m/%Y %H:%M:%S"),
                    "tecnico": tecnico,
                    "serie": serie,
                    "contrato": contrato,
                })
                st.success("Análise concluída! Vá para as abas de Pré-visualização e Frames.")

# --- TAB 2: Pré-visualização ---
with tabs[1]:
    st.markdown("### 2) Pré-visualização do vídeo")
    state = st.session_state[K_STATE]
    if state["temp_video_path"] and os.path.exists(state["temp_video_path"]):
        cols = st.columns(VIDEO_COLS)  # ~25% da largura total
        with cols[0]:
            st.video(state["temp_video_path"], format="video/mp4", start_time=0)
            st.caption(f"Arquivo: {state['filename']} — Duração: {round(state['duration'], 2)}s")
    else:
        st.info("Envie um vídeo na aba **Upload**.")

# --- TAB 3: Frames ---
with tabs[2]:
    st.markdown("### 3) Frames extraídos")
    state = st.session_state[K_STATE]
    frames = state["frames"]
    if frames:
        # Header simples
        c1, c2 = st.columns([1, 1])
        with c1:
            st.write(f"Total de frames: **{len(frames)}**")
        with c2:
            st.write(f"Duração: **{round(state['duration'], 2)}s**")

        thumb_w = st.slider("Tamanho das miniaturas (px)", 120, 320, THUMB_WIDTH, 10, key="thumb_w_v1")

        # Mostra os 10 frames
        cols = st.columns(GRID_COLS)  # grade fixa
        for i, fr in enumerate(frames):
            with cols[i % GRID_COLS]:
                caption = f"Frame {int(fr.get('frame_number', i+1))} — t={str(fr.get('timestamp','?'))}s"
                _safe_show_image(fr, int(thumb_w), caption)
    else:
        st.info("Nenhum frame disponível. Faça o upload na aba **Upload**.")

# --- TAB 4: Relatório ---
with tabs[3]:
    st.markdown("### 4) Relatório")
    state = st.session_state[K_STATE]
    if state["frames"]:
        report = build_report_text(state)
        st.text_area("Prévia do relatório", report, height=260, key="report_preview_v1")

        # .txt isolado (opcional)
        st.download_button(
            "📥 Baixar relatório (.txt)",
            data=report.encode("utf-8"),
            file_name="relatorio_analise_video_tecnico.txt",
            mime="text/plain",
            key="dl_report_v1"
        )

        # Pacote completo (.zip): relatório + frames + vídeo (pasta com CONTRATO + Nº de SÉRIE)
        zip_bytes, zip_name = build_zip_package(state)
        st.download_button(
            "📦 Baixar pacote completo (.zip)",
            data=zip_bytes,
            file_name=zip_name,
            mime="application/zip",
            key="dl_zip_v1"
        )
    else:
        st.info("Gere uma análise primeiro na aba **Upload**.")

# --- TAB 5: Nova análise ---
with tabs[4]:
    st.markdown("### Nova análise")
    st.info("Redefinindo a análise e retornando para **Upload**...")
    _reset_analysis()
