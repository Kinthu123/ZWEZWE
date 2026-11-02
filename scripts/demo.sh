#!/usr/bin/env bash
# Start the Folio Help Desk for a live demo on the local network.
# Checks Ollama and the models first, prints the URLs, and keeps the laptop awake while it runs.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
OLLAMA="${OLLAMA_HOST:-http://localhost:11434}"

if [ ! -x .venv/bin/uvicorn ]; then
  echo "No virtual environment found. Run the install step in README.md first." >&2
  exit 1
fi
if ! curl -s -m 3 "$OLLAMA/api/version" >/dev/null; then
  echo "Ollama is not running at $OLLAMA. Start the Ollama app (or run: ollama serve) and try again." >&2
  exit 1
fi
for model in "${RAG_EMBED_MODEL:-embeddinggemma}" "${RAG_CHAT_MODEL:-qwen3:8b}"; do
  if ! ollama show "$model" >/dev/null 2>&1; then
    echo "Model $model is missing. Run: ollama pull $model" >&2
    exit 1
  fi
done

IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)"
echo "Folio Help Desk"
echo "  On this laptop:            http://localhost:$PORT"
if [ -n "$IP" ]; then
  echo "  On a phone, same Wi-Fi:    http://$IP:$PORT"
fi
echo "  API docs:                  http://localhost:$PORT/docs"
echo "Startup indexes the documents and warms up the model (about 10 seconds). Press Ctrl+C to stop."

KEEP_AWAKE=()
if command -v caffeinate >/dev/null; then
  KEEP_AWAKE=(caffeinate -i)
fi
exec "${KEEP_AWAKE[@]}" .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
