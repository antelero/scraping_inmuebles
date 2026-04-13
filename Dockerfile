# Imagen base
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# 🔴 Instalar certificados PRIMERO (clave)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    openssl \
    curl \
    gnupg \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y nodejs npm

# Verificación
RUN node -v && npm -v

# Directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

#Asegurar pip actualizado + certificados Python
RUN python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --upgrade pip certifi

#Instalar dependencias Python
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Copiar resto del proyecto
COPY . .

CMD ["python", "main_scrap.py"]