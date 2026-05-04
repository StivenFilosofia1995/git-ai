#!/usr/bin/env sh
set -e

export PORT="${PORT:-8000}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"

# Iniciar Ollama en background para el chat
ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

cleanup() {
  kill "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Esperar max 30s a que Ollama arranque
i=1
while [ "$i" -le 30 ]; do
  if curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    echo "[start.sh] Ollama listo"
    if ! ollama list 2>/dev/null | grep -F "$MODEL" >/dev/null 2>&1; then
      echo "[start.sh] Descargando modelo $MODEL..."
      ollama pull "$MODEL" || echo "[start.sh] No se pudo descargar el modelo, continuando sin el"
    fi
    break
  fi
  sleep 1
  i=$((i + 1))
done

if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "[start.sh] Ollama no disponible — la app funcionara sin LLM local"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
