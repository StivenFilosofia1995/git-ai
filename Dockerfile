# ── Stage 1: Build frontend ──
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY compas-cultural/frontend/package.json compas-cultural/frontend/package-lock.json* ./
RUN npm ci
COPY compas-cultural/frontend/ .
# API is same-origin, so VITE_API_BASE_URL = /api/v1
ENV VITE_API_BASE_URL=/api/v1
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_MAPBOX_TOKEN
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
ENV VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN
RUN npm run build

# ── Stage 2: Python backend + static frontend ──
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY compas-cultural/backend/requirements-prod.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY compas-cultural/backend/ .

# Copy compiled frontend into /app/static
COPY --from=frontend-build /frontend/dist ./static

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
