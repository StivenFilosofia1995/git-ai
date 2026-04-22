FROM python:3.11-slim

WORKDIR /app

# System build deps only (gcc for C extensions).
# Playwright --with-deps will install its own Chromium system libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python packages AND Playwright browser in the same layer so the
# browser binary always matches the installed playwright package version.
# --with-deps installs Chromium's system libraries automatically.
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

# Railway assigns PORT dynamically
ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
