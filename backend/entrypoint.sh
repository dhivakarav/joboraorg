#!/bin/sh
# Production entrypoint: apply DB migrations, then start the API.
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting Jobara API on port ${PORT:-8000}..."
# Railway/Render inject $PORT; default to 8000 for local/docker-compose.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
