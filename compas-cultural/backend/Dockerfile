FROM python:3.11-slim

WORKDIR /app

ENV EASYOCR_MODULE_PATH=/opt/easyocr-models

# System deps + Ollama + librerías de Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ca-certificates \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Instalar Python deps + Playwright chromium
# NOTA: NO pre-descargamos modelos de EasyOCR en el build (eso causa OOM en Railway)
# Los modelos se descargan automáticamente en la primera llamada OCR
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium \
    && mkdir -p ${EASYOCR_MODULE_PATH}

COPY . .

RUN chmod +x /app/start.sh

# Railway assigns PORT dynamically
ENV PORT=8000
EXPOSE ${PORT}

CMD ["/app/start.sh"]
