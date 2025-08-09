#!/bin/bash

echo "🎥 Instalando Analisador de Vídeo Técnico..."

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado. Por favor, instale Python 3.8+ primeiro."
    exit 1
fi

# Verificar se pip está instalado
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 não encontrado. Por favor, instale pip primeiro."
    exit 1
fi

# Criar ambiente virtual (opcional)
read -p "Deseja criar um ambiente virtual? (y/n): " create_venv
if [[ $create_venv == "y" || $create_venv == "Y" ]]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
    
    # Ativar ambiente virtual
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    echo "✅ Ambiente virtual criado e ativado"
fi

# Atualizar pip
echo "⬆️ Atualizando pip..."
pip3 install --upgrade pip

# Instalar dependências
echo "📥 Instalando dependências..."
pip3 install -r requirements.txt

# Verificar instalação do OpenCV
echo "🔍 Verificando instalação do OpenCV..."
python3 -c "import cv2; print('✅ OpenCV instalado com sucesso:', cv2.__version__)" 2>/dev/null || {
    echo "⚠️ Problemas com OpenCV. Tentando instalação alternativa..."
    pip3 install opencv-python-headless
}

# Criar diretórios necessários
echo "📁 Criando diretórios..."
mkdir -p uploads
mkdir -p frames

# Verificar se tudo está funcionando
echo "🧪 Testando instalação..."
python3 -c "
import flask
import cv2
import PIL
import numpy
print('✅ Todas as dependências instaladas com sucesso!')
print('Flask:', flask.__version__)
print('OpenCV:', cv2.__version__)
print('Pillow:', PIL.__version__)
print('NumPy:', numpy.__version__)
" || {
    echo "❌ Erro na verificação das dependências"
    exit 1
}

echo ""
echo "🎉 Instalação concluída com sucesso!"
echo ""
echo "📋 Para executar o sistema:"
echo "   python3 app.py"
echo ""
echo "🌐 Acesse no navegador:"
echo "   http://localhost:8080"
echo ""

# Perguntar se quer executar agora
read -p "Deseja executar o sistema agora? (y/n): " run_now
if [[ $run_now == "y" || $run_now == "Y" ]]; then
    echo "🚀 Iniciando sistema..."
    python3 app.py
fi

