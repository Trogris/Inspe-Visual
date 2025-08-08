import streamlit as st
import cv2
import tempfile
import os
import zipfile
from io import BytesIO

def extract_frames(video_path, intervalo_s=3):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps == 0:
        return [], 0
    intervalo = int(fps * intervalo_s)
    frame_number = 0
    frames = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_number % intervalo == 0:
            _, img_bytes = cv2.imencode('.jpg', frame)
            frames.append(img_bytes.tobytes())
        frame_number += 1

    cap.release()
    return frames, fps

st.title("Extrair e Salvar Frames de Vídeo")
st.write("Preencha os dados abaixo, envie seu vídeo e baixe as imagens extraídas a cada 3 segundos junto com o vídeo original em um arquivo ZIP.")

nome = st.text_input("Nome do operador")
num_serie = st.text_input("Número de série do equipamento")
uploaded_file = st.file_uploader("Selecione o vídeo", type=['mp4', 'mov', 'avi'])

if uploaded_file is not None and nome and num_serie:
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tfile:
        tfile.write(uploaded_file.read())
        temp_video_path = tfile.name

    with st.spinner("Extraindo frames..."):
        frames, fps = extract_frames(temp_video_path, intervalo_s=3)

    if not frames:
        st.error("Não foi possível abrir o vídeo ou vídeo não suportado.")
    else:
        st.success(f"Total de frames extraídos: {len(frames)}")
        st.info("Visualização das imagens extraídas:")

        for idx, img_bytes in enumerate(frames):
            st.image(img_bytes, caption=f"Frame {idx}", use_column_width=True)

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for idx, img_bytes in enumerate(frames):
                zip_file.writestr(f"{nome}_{num_serie}_frame_{idx}.jpg", img_bytes)
            with open(temp_video_path, "rb") as f:
                zip_file.writestr(f"{nome}_{num_serie}_video.mp4", f.read())
        zip_buffer.seek(0)

        st.download_button(
            label="Baixar todas as imagens e vídeo em ZIP",
            data=zip_buffer,
            file_name=f"{nome}_{num_serie}_imagens_e_video.zip",
            mime="application/zip"
        )

    os.remove(temp_video_path)
else:
    st.info("Preencha nome, número de série e faça upload do vídeo.")
