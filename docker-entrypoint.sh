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

# 启动 FastAPI
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
