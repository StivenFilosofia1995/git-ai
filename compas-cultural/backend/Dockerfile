FROM python:3.11-slim

WORKDIR /app

# System build deps only (gcc for C extensions).
# Playwright --with-deps will install its own Chromium system libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ca-certificates \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python packages AND Playwright browser in the same layer so the
# browser binary always matches the installed playwright package version.
# --with-deps installs Chromium's system libraries automatically.
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

RUN chmod +x /app/start.sh

# Railway assigns PORT dynamically
ENV PORT=8000
EXPOSE ${PORT}

CMD ["/app/start.sh"]
