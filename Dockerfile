FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg2 and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies from backend project
COPY compas-cultural/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend app source from monorepo
COPY compas-cultural/backend/ .

ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
