# 脚本使用说明

本目录用于存放本地开发常用脚本，包括 Docker 容器管理和 FastAPI 后端服务管理。

## 一键启动

启动 PostgreSQL、Redis 和 FastAPI 后端服务：

```powershell
.\scripts\start.ps1
```

启动后可访问接口文档：

```text
http://127.0.0.1:8000/docs
```

以自动重载模式启动后端，适合开发时修改代码后自动重启：

```powershell
.\scripts\start.ps1 -Reload
```

以前台模式启动后端，适合查看实时日志：

```powershell
.\scripts\start.ps1 -Foreground
```

启动后端后继续以前台方式启动 Celery worker，用于执行公众号和 B站真实发布任务：

```powershell
.\scripts\start.ps1 -Worker
```

只启动指定容器服务后再启动后端：

```powershell
.\scripts\start.ps1 postgres
```

## 一键关闭

关闭 FastAPI 后端服务，并关闭 PostgreSQL、Redis 容器，保留数据卷：

```powershell
.\scripts\stop.ps1
```

> ⚠️ **不要手动执行 `docker compose down -v`**，该命令会删除 PostgreSQL 数据卷，导致所有账号设置、发布记录等数据永久丢失。

关闭服务并删除数据卷：

```powershell
.\scripts\stop.ps1 -RemoveVolumes
```

只有在需要重置本地 PostgreSQL 数据时，才使用 `-RemoveVolumes`。

## 单独启动后端服务

后台启动 FastAPI 后端服务：

```powershell
.\scripts\start-backend.ps1
```

启动后可访问接口文档：

```text
http://127.0.0.1:8000/docs
```

以自动重载模式启动，适合开发时修改代码后自动重启：

```powershell
.\scripts\start-backend.ps1 -Reload
```

以前台模式启动，适合查看实时日志：

```powershell
.\scripts\start-backend.ps1 -Foreground
```

后端进程 PID 会写入：

```text
logs/backend.pid
```

后端日志会写入：

```text
logs/backend.out.log
logs/backend.err.log
```

## 单独启动 Celery Worker

前台启动真实发布任务 worker：

```powershell
.\scripts\start-worker.ps1
```

worker 日志会写入：

```text
logs/worker.out.log
```

## 单独关闭 Celery Worker

前台 worker 使用 `Ctrl+C` 关闭。如果未来改为后台方式运行，可使用：

```powershell
.\scripts\stop-worker.ps1
```

## 单独关闭后端服务

关闭 `logs/backend.pid` 记录的后端进程：

```powershell
.\scripts\stop-backend.ps1
```

如果 PID 文件不存在，但 8000 端口仍被后端占用，可按端口关闭：

```powershell
.\scripts\stop-backend.ps1 -ByPort
```

## 单独启动容器

启动 PostgreSQL 和 Redis：

```powershell
.\scripts\start-containers.ps1
```

只启动 PostgreSQL：

```powershell
.\scripts\start-containers.ps1 postgres
```

只启动 Redis：

```powershell
.\scripts\start-containers.ps1 redis
```

## 单独关闭容器

关闭容器并保留数据卷：

```powershell
.\scripts\stop-containers.ps1
```

关闭容器并删除数据卷：

```powershell
.\scripts\stop-containers.ps1 -RemoveVolumes
```

只有在需要重置本地 PostgreSQL 数据时，才使用 `-RemoveVolumes`。

## 后端本地验证流程

启动 PostgreSQL 后，可以运行后端服务：

```powershell
conda activate auto_upt
uvicorn backend.app.main:app --reload
```

后端默认连接的 PostgreSQL 地址是：

```text
postgresql+asyncpg://auto_upt:auto_upt@localhost:5432/auto_upt
```

第二阶段引入 Alembic 管理数据库结构。空库初始化可以运行：

```powershell
alembic upgrade head
```
