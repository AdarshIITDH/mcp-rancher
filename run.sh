#!/bin/bash
# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
uvicorn app.main:app --host 0.0.0.0 --reload --port 8000
