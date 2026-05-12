FROM python:3.11-slim

WORKDIR /app

ENV EASYOCR_MODULE_PATH=/opt/easyocr-models

# System deps + Ollama (para desarrollo local; en Railway usa Groq/Gemini)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ca-certificates \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

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
