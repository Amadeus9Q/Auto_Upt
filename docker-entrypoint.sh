#!/bin/bash
set -e

# 等待 PostgreSQL 就绪
echo "Waiting for PostgreSQL..."
until pg_isready -h postgres -U auto_upt -d auto_upt 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL ready."

# 运行数据库迁移
cd /app
python -m alembic upgrade head

# Compose may provide a service-specific command, such as the Celery worker.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# Default to the FastAPI server when no command is provided.
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
