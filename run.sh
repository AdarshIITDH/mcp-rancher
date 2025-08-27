#!/bin/bash
# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
uvicorn app.main:app --reload --port 8000
