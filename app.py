from flask import Flask, render_template_string, request, jsonify, send_file
import os
import base64
import cv2
import numpy as np
from datetime import datetime
from PIL import Image
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['FRAMES_FOLDER'] = 'frames'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

# Criar pastas necessárias
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['FRAMES_FOLDER'], exist_ok=True)

# Template HTML
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analisador de Vídeo Técnico</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 2.5em;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #555;
        }
        input[type="text"], input[type="file"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
        }
        input[type="file"] {
            padding: 10px;
        }
        button {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            margin: 10px 5px;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        .video-container {
            margin: 20px 0;
            text-align: center;
        }
        video {
            max-width: 100%;
            border-radius: 8px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .frames-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .frame-item {
            text-align: center;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .frame-image {
            width: 100%;
            height: 120px;
            object-fit: cover;
            border-radius: 5px;
            margin-bottom: 8px;
        }
        .success { 
            color: #28a745; 
            font-weight: bold; 
            background: #d4edda;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }
        .error { 
            color: #dc3545; 
            font-weight: bold;
            background: #f8d7da;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }
        .hidden { display: none; }
        .report {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .report h3 {
            color: #333;
            margin-bottom: 15px;
        }
        .report-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        .loading {
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Analisador de Vídeo Técnico</h1>
        
        <form id="videoForm" enctype="multipart/form-data">
            <div class="form-group">
                <label for="tecnico">Nome do Técnico:</label>
                <input type="text" id="tecnico" name="tecnico" required>
            </div>
            
            <div class="form-group">
                <label for="serie">Número de Série do Equipamento:</label>
                <input type="text" id="serie" name="serie" required>
            </div>
            
            <div class="form-group">
                <label for="video">Selecionar Vídeo (20-30 segundos):</label>
                <input type="file" id="video" name="video" accept="video/*" required>
                <small>Formatos: MP4, MOV, AVI, MKV, WMV | Máximo: 200MB</small>
            </div>
            
            <button type="submit">📤 Enviar e Analisar</button>
        </form>
        
        <div id="loading" class="loading hidden">
            <div class="spinner"></div>
            <p>Processando vídeo e extraindo frames...</p>
        </div>
        
        <div id="result" class="hidden">
            <div class="success">
                <strong>✅ Vídeo processado com sucesso!</strong>
            </div>
            
            <div class="video-container">
                <h3>📹 Vídeo Enviado:</h3>
                <video id="videoPlayer" controls>
                    Seu navegador não suporta reprodução de vídeo.
                </video>
            </div>
            
            <div>
                <h3>🖼️ Frames Extraídos (10 frames):</h3>
                <div class="frames-grid" id="framesGrid">
                    <!-- Frames reais serão inseridos aqui -->
                </div>
            </div>
            
            <div class="report" id="reportSection">
                <h3>📋 Relatório de Análise</h3>
                <div id="reportContent">
                    <!-- Relatório será inserido aqui -->
                </div>
            </div>
            
            <button onclick="downloadReport()">📄 Baixar Relatório</button>
            <button onclick="newAnalysis()">🔄 Nova Análise</button>
        </div>
    </div>

    <script>
        document.getElementById('videoForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            const tecnico = document.getElementById('tecnico').value;
            const serie = document.getElementById('serie').value;
            const videoFile = document.getElementById('video').files[0];
            
            if (!videoFile) {
                alert('Por favor, selecione um vídeo!');
                return;
            }
            
            // Validar tamanho
            if (videoFile.size > 200 * 1024 * 1024) {
                alert('Arquivo muito grande! Máximo 200MB.');
                return;
            }
            
            formData.append('tecnico', tecnico);
            formData.append('serie', serie);
            formData.append('video', videoFile);
            
            // Mostrar loading
            document.getElementById('loading').classList.remove('hidden');
            const button = document.querySelector('button[type="submit"]');
            button.textContent = '⏳ Processando...';
            button.disabled = true;
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loading').classList.add('hidden');
                if (data.success) {
                    showResult(data);
                } else {
                    alert('Erro: ' + data.error);
                }
            })
            .catch(error => {
                document.getElementById('loading').classList.add('hidden');
                alert('Erro no upload: ' + error);
            })
            .finally(() => {
                button.textContent = '📤 Enviar e Analisar';
                button.disabled = false;
            });
        });
        
        function showResult(data) {
            // Mostrar seção de resultado
            document.getElementById('result').classList.remove('hidden');
            
            // Configurar player de vídeo
            const video = document.getElementById('videoPlayer');
            video.src = '/video/' + data.filename;
            
            // Mostrar frames reais
            showFrames(data.frames);
            
            // Gerar relatório
            generateReport(data);
            
            // Scroll para resultado
            document.getElementById('result').scrollIntoView({ behavior: 'smooth' });
        }
        
        function showFrames(frames) {
            const grid = document.getElementById('framesGrid');
            grid.innerHTML = '';
            
            frames.forEach((frame, index) => {
                const frameDiv = document.createElement('div');
                frameDiv.className = 'frame-item';
                
                frameDiv.innerHTML = `
                    <img src="data:image/jpeg;base64,${frame.image}" 
                         alt="Frame ${index + 1}" 
                         class="frame-image">
                    <small><strong>Frame ${index + 1}</strong><br>
                    Tempo: ${frame.timestamp}s</small>
                `;
                
                grid.appendChild(frameDiv);
            });
        }
        
        function generateReport(data) {
            const reportContent = document.getElementById('reportContent');
            reportContent.innerHTML = `
                <div class="report-item">
                    <span>Técnico Responsável:</span>
                    <span>${data.tecnico}</span>
                </div>
                <div class="report-item">
                    <span>Número de Série:</span>
                    <span>${data.serie}</span>
                </div>
                <div class="report-item">
                    <span>Arquivo de Vídeo:</span>
                    <span>${data.filename}</span>
                </div>
                <div class="report-item">
                    <span>Tamanho:</span>
                    <span>${(data.size / (1024*1024)).toFixed(1)} MB</span>
                </div>
                <div class="report-item">
                    <span>Duração:</span>
                    <span>${data.duration} segundos</span>
                </div>
                <div class="report-item">
                    <span>Frames Extraídos:</span>
                    <span>10 frames</span>
                </div>
                <div class="report-item">
                    <span>Data/Hora:</span>
                    <span>${data.timestamp}</span>
                </div>
            `;
        }
        
        function downloadReport() {
            window.open('/download-report', '_blank');
        }
        
        function newAnalysis() {
            document.getElementById('result').classList.add('hidden');
            document.getElementById('videoForm').reset();
            document.querySelector('h1').scrollIntoView({ behavior: 'smooth' });
        }
    </script>
</body>
</html>
'''

def extract_frames_from_video(video_path, num_frames=10):
    """Extrai frames reais do vídeo usando OpenCV"""
    try:
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        
        frames = []
        frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
        
        for i, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if ret:
                # Converter BGR para RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Redimensionar se necessário
                height, width = frame_rgb.shape[:2]
                if width > 400:
                    new_width = 400
                    new_height = int(height * (new_width / width))
                    frame_rgb = cv2.resize(frame_rgb, (new_width, new_height))
                
                # Converter para PIL Image
                pil_image = Image.fromarray(frame_rgb)
                
                # Converter para base64
                buffer = io.BytesIO()
                pil_image.save(buffer, format='JPEG', quality=85)
                img_base64 = base64.b64encode(buffer.getvalue()).decode()
                
                timestamp = round(frame_idx / fps, 1) if fps > 0 else i * (duration / num_frames)
                
                frames.append({
                    'image': img_base64,
                    'timestamp': timestamp,
                    'frame_number': i + 1
                })
        
        cap.release()
        return frames, duration
        
    except Exception as e:
        print(f"Erro ao extrair frames: {str(e)}")
        return [], 0

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_video():
    try:
        tecnico = request.form.get('tecnico')
        serie = request.form.get('serie')
        video_file = request.files.get('video')
        
        if not video_file:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'})
        
        # Salvar arquivo
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{video_file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        video_file.save(filepath)
        
        # Extrair frames reais
        frames, duration = extract_frames_from_video(filepath)
        
        if not frames:
            return jsonify({'success': False, 'error': 'Falha ao extrair frames do vídeo'})
        
        file_size = os.path.getsize(filepath)
        
        return jsonify({
            'success': True,
            'tecnico': tecnico,
            'serie': serie,
            'filename': filename,
            'size': file_size,
            'duration': round(duration, 1),
            'frames': frames,
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro no processamento: {str(e)}'})

@app.route('/video/<filename>')
def serve_video(filename):
    try:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    except:
        return "Vídeo não encontrado", 404

@app.route('/download-report')
def download_report():
    try:
        report_content = f"""
RELATÓRIO DE ANÁLISE DE VÍDEO TÉCNICO
===================================

Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

INFORMAÇÕES BÁSICAS:
- Técnico Responsável: [Preenchido pelo usuário]
- Número de Série: [Preenchido pelo usuário]
- Arquivo de Vídeo: [Nome do arquivo]

ANÁLISE TÉCNICA:
- Frames Extraídos: 10 frames reais
- Duração: [Calculada automaticamente]
- Tamanho do Arquivo: [MB]
- Formato: [Detectado automaticamente]

CHECKLIST DE VERIFICAÇÃO:
□ Equipamento claramente visível no vídeo
□ Todos os componentes principais identificados
□ Qualidade de imagem adequada para análise
□ Duração apropriada (20-30 segundos)
□ Ângulos de filmagem corretos
□ Iluminação adequada
□ Foco correto em todos os frames
□ Ausência de obstruções visuais
□ Componentes em posição correta
□ Equipamento em estado final de montagem

OBSERVAÇÕES TÉCNICAS:
_________________________________
_________________________________
_________________________________

APROVAÇÃO:
□ Equipamento APROVADO para próxima etapa
□ Equipamento REPROVADO - necessita correções

Assinatura do Técnico: _______________

Data: _______________
"""
        
        # Salvar relatório temporário
        report_path = '/tmp/relatorio_video_tecnico.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return send_file(report_path, as_attachment=True, 
                        download_name='relatorio_analise_video_tecnico.txt')
        
    except Exception as e:
        return f"Erro ao gerar relatório: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)

