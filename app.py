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

import streamlit as st
import numpy as np
from PIL import Image

# Config sempre no topo
st.set_page_config(page_title="Analisador de Vídeo Técnico", layout="wide")

# ========= Parâmetros =========
NUM_FRAMES   = 10
TARGET_WIDTH = 480
GRID_COLS    = 5
THUMB_WIDTH  = 160
VIDEO_COLS   = [1, 3]
TZ_BR = ZoneInfo("America/Sao_Paulo")

# ========= Chaves de estado =========
K_UPLOAD    = "upload_video_v1"
K_TECNICO   = "input_tecnico_v1"
K_SERIE     = "input_serie_v1"
K_CONTRATO  = "input_contrato_v1"
K_STATE     = "state_video_meta_v1"

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm"}

# ========= Sessão =========
def init_session():
    if K_STATE not in st.session_state:
        st.session_state[K_STATE] = {
            "temp_dir": None,
            "filename": None,
            "temp_video_path": None,
            "duration": 0.0,
            "num_frames": 0,
            "frames": [],
            "timestamp_run": None,
            "tecnico": "",
            "serie": "",
            "contrato": "",
        }

def allowed_file(name: str) -> bool:
    if not name:
        return False
    return os.path.splitext(name)[1].lower() in ALLOWED_EXTENSIONS

def _slugify(text: str, fallback: str = "sem_valor") -> str:
    if not text:
        return fallback
    t = text.strip()
    t = re.sub(r"[^\w\s-]", "_", t, flags=re.UNICODE)
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_.")
    return t or fallback

def try_import_cv2():
    try:
        import cv2  # import tardio
        try:
            cv2.setNumThreads(1)
        except Exception:
            pass
        return cv2, None
    except Exception as e:
        return None, e

def extract_frames_from_video(video_path: str, num_frames: int = NUM_FRAMES, target_width: int = TARGET_WIDTH):
    cv2, err = try_import_cv2()
    if cv2 is None:
        raise RuntimeError(
            "OpenCV (cv2) não está disponível. Instale: pip install opencv-python-headless"
        ) from err

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
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok or frame is None:
            t_sec = idx / fps if fps > 0 else 0
            cap.set(cv2.CAP_PROP_POS_MSEC, float(t_sec * 1000.0))
            ok, frame = cap.read()
        if not ok or frame is None:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = frame_rgb.shape
        if w > target_width:
            new_w = target_width
            new_h = int(h * (target_width / w))
            frame_rgb = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        arr = np.ascontiguousarray(frame_rgb, dtype=np.uint8)
        buff = io.BytesIO()
        Image.fromarray(arr).save(buff, format="JPEG", quality=85, optimize=True, progressive=True)
        jpg_bytes = buff.getvalue()

        frames.append({
            "arr": arr,
            "jpg_bytes": jpg_bytes,
            "timestamp": round(idx / fps, 2),
            "frame_number": int(i + 1),
            "shape": tuple(arr.shape),
            "dtype": str(arr.dtype),
        })

    cap.release()
    return frames, duration

@st.cache_data(show_spinner=False, max_entries=8)
def cached_extract(video_bytes: bytes, num_frames: int, target_width: int):
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        tf.write(video_bytes)
        tmp_path = tf.name
    try:
        frames, duration = extract_frames_from_video(tmp_path, num_frames, target_width)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
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
    w = int(max(1, width_px))

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

    if img is None:
        jpg_bytes = fr.get("jpg_bytes")
        if isinstance(jpg_bytes, (bytes, bytearray, memoryview)) and len(jpg_bytes) > 0:
            try:
                tmp = Image.open(io.BytesIO(bytes(jpg_bytes)))
                img = tmp.convert("RGB")
            except Exception:
                img = None

    if img is None:
        st.warning(f"Falha ao renderizar {caption}.")
        return

    try:
        st.image(img, caption=caption, width=w, use_container_width=False, output_format="PNG")
        return
    except Exception:
        pass

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
    serie_slug = _slugify(state.get("serie", ""))
    contrato_slug = _slugify(state.get("contrato", ""))
    folder_slug = f"{contrato_slug}_{serie_slug}".strip("_") or "pacote"
    base_dir = f"{folder_slug}/"

    report_txt = build_report_text(state).encode("utf-8")

    video_path = state.get("temp_video_path")
    video_bytes = None
    video_name = None
    if video_path and os.path.exists(video_path):
        video_name = Path(state.get("filename") or Path(video_path).name).name
        with open(video_path, "rb") as vf:
            video_bytes = vf.read()

    frames = state.get("frames", [])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(base_dir + "relatorio_analise_video_tecnico.txt", report_txt)
        if video_bytes is not None and video_name:
            zf.writestr(base_dir + video_name, video_bytes)
        for f in frames:
            n = int(f.get("frame_number", 0))
            jpg = f.get("jpg_bytes")
            if isinstance(jpg, (bytes, bytearray, memoryview)) and len(jpg) > 0:
                zf.writestr(base_dir + f"frames/frame_{n:02d}.jpg", bytes(jpg))

    zip_bytes = buf.getvalue()
    zip_filename = f"pacote_{folder_slug}.zip"
    return zip_bytes, zip_filename

def handle_reset_if_requested():
    # Usa APIs estáveis: st.query_params e st.rerun
    qp = st.query_params
    if qp.get("reset", None) == "1":
        try:
            temp_dir = st.session_state.get(K_STATE, {}).get("temp_dir")
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

def tab_upload():
    st.markdown("### 1) Envie o vídeo e os dados")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_input("Nome do Técnico", key=K_TECNICO)
    with col2:
        st.text_input("Número de Série do Equipamento", key=K_SERIE)
    with col3:
        st.text_input("Contrato", key=K_CONTRATO)

    video_file = st.file_uploader(
        "Selecionar Vídeo (até 200MB)",
        type=[e.strip(".") for e in ALLOWED_EXTENSIONS],
        key=K_UPLOAD
    )

    processar = st.button("📤 Enviar e Analisar", use_container_width=True, key="btn_enviar_v1")
    if processar:
        if not video_file or not video_file.name:
            st.error("Nenhum arquivo enviado.")
            return
        if not allowed_file(video_file.name):
            st.error("Formato não suportado.")
            return

        tmpdir = tempfile.mkdtemp(prefix="vid_")
        st.session_state[K_STATE]["temp_dir"] = tmpdir
        safe_name = os.path.basename(video_file.name).replace(" ", "_")
        video_path = os.path.join(tmpdir, f"{datetime.now(TZ_BR).strftime('%Y%m%d_%H%M%S')}_{safe_name}")
        with open(video_path, "wb") as f:
            f.write(video_file.read())

        # Aviso de duração (não bloqueante)
        try:
            cv2, _ = try_import_cv2()
            if cv2 is not None:
                cap_tmp = cv2.VideoCapture(video_path)
                fps_tmp = cap_tmp.get(cv2.CAP_PROP_FPS) or 0
                total_tmp = int(cap_tmp.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                cap_tmp.release()
                if fps_tmp > 0 and total_tmp > 0:
                    dur_tmp = total_tmp / fps_tmp
                    if not (20 <= dur_tmp <= 40):
                        st.info(f"Atenção: vídeo com {dur_tmp:.2f}s (recomendado entre 20 e 40s).")
        except Exception:
            pass

        with open(video_path, "rb") as rf:
            video_bytes = rf.read()
        with st.spinner("Processando vídeo e extraindo frames..."):
            try:
                frames, duration = cached_extract(video_bytes, NUM_FRAMES, TARGET_WIDTH)
            except Exception as e:
                st.error(f"Falha ao extrair frames: {e}")
                return

        if not frames:
            st.error("Falha ao extrair frames. Verifique o codec do vídeo.")
        else:
            st.session_state[K_STATE] = {
                "temp_dir": tmpdir,
                "filename": safe_name,
                "temp_video_path": video_path,
                "duration": float(duration),
                "num_frames": len(frames),
                "frames": frames,
                "timestamp_run": datetime.now(TZ_BR).strftime("%d/%m/%Y %H:%M:%S"),
                "tecnico": st.session_state.get(K_TECNICO, ""),
                "serie": st.session_state.get(K_SERIE, ""),
                "contrato": st.session_state.get(K_CONTRATO, ""),
            }
            st.success("Análise concluída! Vá para as abas de Pré-visualização e Frames.")

def tab_preview():
    st.markdown("### 2) Pré-visualização do vídeo")
    state = st.session_state[K_STATE]
    if state["temp_video_path"] and os.path.exists(state["temp_video_path"]):
        cols = st.columns(VIDEO_COLS)
        with cols[0]:
            st.video(state["temp_video_path"], format="video/mp4", start_time=0)
            st.caption(f"Arquivo: {state['filename']} — Duração: {round(state['duration'], 2)}s")
    else:
        st.info("Envie um vídeo na aba **Upload**.")

def tab_frames():
    st.markdown("### 3) Frames extraídos")
    state = st.session_state[K_STATE]
    frames = state["frames"]
    if frames:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.write(f"Total de frames: **{len(frames)}**")
        with c2:
            st.write(f"Duração: **{round(state['duration'], 2)}s**")

        thumb_w = st.slider("Tamanho das miniaturas (px)", 120, 320, THUMB_WIDTH, 10, key="thumb_w_v1")

        cols = st.columns(GRID_COLS)
        for i, fr in enumerate(frames):
            with cols[i % GRID_COLS]:
                caption = f"Frame {int(fr.get('frame_number', i+1))} — t={str(fr.get('timestamp','?'))}s"
                _safe_show_image(fr, int(thumb_w), caption)
    else:
        st.info("Nenhum frame disponível. Faça o upload na aba **Upload**.")

def tab_report():
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

        zip_bytes, zip_name = build_zip_package(state)
        st.download_button(
            "📦 Baixar pacote completo (.zip)",
            data=zip_bytes,
            file_name=zip_name,
            mime="application/zip",
            key="dl_zip_v1"
        )

        st.divider()
        if st.button("Nova análise", type="primary", use_container_width=False, key="btn_reset_from_report"):
            st.query_params["reset"] = "1"
            st.rerun()
    else:
        st.info("Gere uma análise primeiro na aba **Upload**.")

def main():
    # 1) Garante sessão
    init_session()

    # 2) Trata reset (agora com sessão garantida)
    handle_reset_if_requested()

    # 3) Layout (tabs)
    tabs = st.tabs(["Upload", "Pré-visualização", "Frames", "Relatório"])

    with tabs[0]:
        tab_upload()
    with tabs[1]:
        tab_preview()
    with tabs[2]:
        tab_frames()
    with tabs[3]:
        tab_report()

if __name__ == "__main__":
    main()
