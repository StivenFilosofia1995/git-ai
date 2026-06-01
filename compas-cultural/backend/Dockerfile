FROM python:3.11-slim

WORKDIR /app

ENV EASYOCR_MODULE_PATH=/opt/easyocr-models

# System deps (Ollama omitido en Docker — Railway usa Groq/Gemini como IA)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps (prod — sin torch/easyocr/playwright para imagen ligera)
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt \
    && mkdir -p ${EASYOCR_MODULE_PATH}

COPY . .

RUN chmod +x /app/start.sh

ENV PORT=8000
EXPOSE ${PORT}

CMD ["/app/start.sh"]
