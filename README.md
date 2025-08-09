# 🎥 Analisador de Vídeo Técnico

Sistema web para análise técnica de vídeos de equipamentos, com extração automática de frames e geração de relatórios.

## 📋 Funcionalidades

- **Upload de Vídeo**: Suporte a múltiplos formatos (MP4, MOV, AVI, MKV, WMV)
- **Pré-visualização**: Player integrado para visualizar o vídeo enviado
- **Extração de Frames**: 10 frames reais extraídos automaticamente do vídeo
- **Relatório Técnico**: Geração automática de relatório com checklist
- **Interface Responsiva**: Design moderno e adaptável a qualquer dispositivo

## 🚀 Como Usar

### 1. Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/analisador-video-tecnico.git
cd analisador-video-tecnico

# Instale as dependências
pip install -r requirements.txt

# Execute o aplicativo
python app.py
```

### 2. Acesso

Abra seu navegador e acesse: `http://localhost:8080`

### 3. Fluxo de Uso

1. **Preencha os dados**: Nome do técnico e número de série do equipamento
2. **Selecione o vídeo**: Arquivo de 20-30 segundos (máximo 200MB)
3. **Envie e analise**: Clique em "📤 Enviar e Analisar"
4. **Visualize os resultados**: 
   - Pré-visualização do vídeo
   - 10 frames extraídos com timestamps
   - Relatório técnico completo
5. **Baixe o relatório**: Arquivo TXT com checklist para preenchimento

## 📁 Estrutura do Projeto

```
analisador-video-tecnico/
├── app.py              # Aplicação principal Flask
├── requirements.txt    # Dependências Python
├── README.md          # Documentação
├── uploads/           # Pasta para vídeos (criada automaticamente)
└── frames/            # Pasta para frames (criada automaticamente)
```

## 🔧 Tecnologias Utilizadas

- **Backend**: Flask (Python)
- **Processamento de Vídeo**: OpenCV
- **Manipulação de Imagens**: Pillow
- **Frontend**: HTML5, CSS3, JavaScript
- **Design**: CSS Grid, Flexbox, Gradientes

## ⚙️ Configurações

### Limites do Sistema
- **Tamanho máximo**: 200MB por vídeo
- **Formatos suportados**: MP4, MOV, AVI, MKV, WMV, MPEG4, WEBM, FLV, 3GP
- **Duração recomendada**: 20-30 segundos
- **Frames extraídos**: 10 frames distribuídos uniformemente

### Validações
- ✅ Verificação de formato de arquivo
- ✅ Validação de tamanho máximo
- ✅ Prevenção de reprocessamento
- ✅ Tratamento de erros robusto

## 📊 Relatório Gerado

O sistema gera um relatório técnico em formato TXT contendo:

- **Informações Básicas**: Técnico, número de série, arquivo
- **Dados Técnicos**: Duração, tamanho, formato, frames
- **Checklist de Verificação**: 10 itens para validação manual
- **Seção de Observações**: Espaço para anotações
- **Aprovação**: Campo para aprovação/reprovação

## 🛠️ Desenvolvimento

### Pré-requisitos
- Python 3.8+
- OpenCV (instalado automaticamente via pip)

### Instalação para Desenvolvimento
```bash
# Clone o repositório
git clone https://github.com/seu-usuario/analisador-video-tecnico.git
cd analisador-video-tecnico

# Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Instale as dependências
pip install -r requirements.txt

# Execute em modo debug
python app.py
```

## 🚀 Deploy

### Heroku
```bash
# Instale o Heroku CLI
# Crie um novo app
heroku create seu-app-name

# Configure as variáveis
heroku config:set FLASK_ENV=production

# Deploy
git push heroku main
```

### Docker
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python", "app.py"]
```

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📞 Suporte

Para suporte, envie um email para: suporte@exemplo.com

## 🔄 Changelog

### v1.0.0 (2025-08-08)
- ✨ Lançamento inicial
- 🎥 Upload e processamento de vídeos
- 🖼️ Extração real de frames com OpenCV
- 📋 Geração de relatórios técnicos
- 📱 Interface responsiva
- ✅ Sistema de validações

---

**Desenvolvido com ❤️ para análise técnica de equipamentos**

