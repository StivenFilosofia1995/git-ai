#!/usr/bin/env sh
set -e

export PORT="${PORT:-8000}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"

# Iniciar Ollama en background (modelo ya está en la imagen — no descarga)
ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

cleanup() {
  kill "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Esperar max 20s a que Ollama arranque (sin descarga, es rápido)
i=1
while [ "$i" -le 20 ]; do
  if curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    echo "[start.sh] Ollama listo con modelo $MODEL"
    break
  fi
  sleep 1
  i=$((i + 1))
done

if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "[start.sh] Ollama no disponible — usando Groq/Gemini como fallback"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
