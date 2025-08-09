# Analisador de Vídeo Técnico (Streamlit)

App Streamlit estável (sem `removeChild`), com:
- Upload de vídeo (20–30s)
- Extração de 10 frames distribuídos
- Pré-visualização do vídeo
- Galeria paginada de frames (4 colunas fixas)
- Relatório TXT para download

## Como rodar
```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8080 --server.address 0.0.0.0
```
Abra: `http://localhost:8080`