FROM python:3.11-slim

WORKDIR /app

# Install system deps (gcc for C extensions + Playwright/Chromium deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    # Playwright Chromium system deps
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (headless browser for JS-heavy sites)
RUN playwright install chromiumo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (headless browser for JS-heavy sites)
RUN playwright install chromium

COPY . .

# Railway assigns PORT dynamically
ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
