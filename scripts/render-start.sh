#!/bin/sh
set -eu

PORT="${PORT:-8501}"

mkdir -p "${STORAGE_PATH:-/app/shared}"

(
    cd /app/backend
    uvicorn main:app --host 127.0.0.1 --port 8000
) &

BACKEND_PID="$!"

cleanup() {
    kill "$BACKEND_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

cd /app/frontend
streamlit run app.py --server.port "$PORT" --server.address 0.0.0.0
