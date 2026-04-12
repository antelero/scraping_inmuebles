# Imagen base con Python
FROM python:3.11-slim

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar Node.js + dependencias necesarias
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean

# Verificar instalación (opcional pero útil)
RUN node -v && npm -v

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero (cachea mejor)
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Comando por defecto
CMD ["python", "main_scrap.py"]