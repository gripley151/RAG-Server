#!/bin/sh
# Starts the Ollama server, waits for it to be ready, then pulls the model
# this project uses so `docker compose up` alone is enough -- no manual
# `ollama pull` step required before grading.
set -e

ollama serve &
SERVE_PID=$!

until ollama list >/dev/null 2>&1; do
  sleep 1
done

ollama pull "${OLLAMA_MODEL:-llama3.2:1b}"

wait $SERVE_PID
