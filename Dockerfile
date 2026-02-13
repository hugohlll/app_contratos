# Usa uma imagem leve do Python
FROM python:3.11-slim

# Evita que o Python gere arquivos .pyc e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Define onde o app vai ficar dentro do container
WORKDIR /app

# Instala dependências do sistema necessárias para compilar pacotes
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências do projeto
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia o código atual para dentro do container
COPY . .

# Expõe a porta 8000
EXPOSE 8000
