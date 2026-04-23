#!/usr/bin/env sh
set -eu

export PORT="${PORT:-8000}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"
export OLLAMA_BOOTSTRAPPED="true"

ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

cleanup() {
  if kill -0 "$OLLAMA_PID" >/dev/null 2>&1; then
    kill "$OLLAMA_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

i=1
while [ "$i" -le 60 ]; do
  if curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  i=$((i + 1))
done

if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "[start.sh] Ollama no inició correctamente"
  exit 1
fi

if ! ollama list | grep -F "$MODEL" >/dev/null 2>&1; then
  echo "[start.sh] Descargando modelo $MODEL"
  ollama pull "$MODEL"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
