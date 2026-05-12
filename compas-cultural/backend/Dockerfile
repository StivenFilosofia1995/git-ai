FROM python:3.11-slim

WORKDIR /app

ENV EASYOCR_MODULE_PATH=/opt/easyocr-models
ENV OLLAMA_MODELS=/root/.ollama/models

# System deps + Ollama
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ca-certificates \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Pre-pull Ollama model at BUILD time so it never downloads at runtime
ARG OLLAMA_MODEL=qwen2.5:1.5b
RUN ollama serve & \
    sleep 8 && \
    ollama pull ${OLLAMA_MODEL} && \
    pkill -f "ollama serve" || true

# Python deps + Playwright chromium
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium \
    && mkdir -p ${EASYOCR_MODULE_PATH}

COPY . .

RUN chmod +x /app/start.sh

ENV PORT=8000
EXPOSE ${PORT}

CMD ["/app/start.sh"]
