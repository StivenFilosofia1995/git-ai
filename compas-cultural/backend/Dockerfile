FROM python:3.11-slim

WORKDIR /app

# System build deps only (gcc for C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Use prod requirements (no PyTorch/EasyOCR/Playwright — saves ~5GB)
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

RUN chmod +x /app/start.sh

# Railway assigns PORT dynamically
ENV PORT=8000
EXPOSE ${PORT}

CMD ["/app/start.sh"]
