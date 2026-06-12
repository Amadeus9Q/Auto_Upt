# Auto_Upt

Auto_Upt 是一个多平台内容创作、适配、预览与发布工作台。

项目采用“内容中台 + 平台 Adapter + AI Agent 编排”的架构，将统一正文、素材和元数据转换为公众号、B站、知乎、小红书等平台草稿，并通过人工确认后的发布任务执行模拟、保存草稿或真实发布。

## 工作流程

前端工作台围绕三个可回退的流程节点组织：

1. **统一内容编译**：编辑标题、正文与标签，管理素材库，在正文指定位置插入图片、视频或音频引用，并选择生成平台。
2. **编辑所选平台**：生成多平台预览，独立调整平台内容，执行单平台或批量智能优化。
3. **发布确认**：检查账号、发布字段、封面和素材，选择模拟、保存草稿或真实发布，并在任务看板查看结果。

未连接账号的平台仍可参与模拟；保存草稿和真实发布仅对已连接且已支持的平台开放。

## 当前能力

### 内容与预览

- 统一编辑标题、正文、标签和目标平台。
- 共享素材库支持图片、视频、音频、封面、多级文件夹和正文素材引用。
- 正文素材标记决定图片在平台内容中的具体位置。
- 生成公众号、B站、知乎和小红书平台草稿与校验报告。
- Agent 支持内容分析、平台风格改写、标题与关键词优化；未配置 LLM 时使用规则回退。

### 账号与发布

- 发布确认中展示账号连接状态、账号名称和平台 ID。
- 未连接平台仅允许模拟，连接完成后可立即用于发布确认。
- 任务看板展示平台步骤、原始失败原因和处理建议。
- 公众号支持正文图片上传、封面上传、创建草稿、提交发布和状态查询。
- B站支持登录凭据保存、视频与封面上传、稿件提交和状态查询。
- 小红书已实现 API Adapter 与字段映射，账号连接和真实联调仍需补齐。
- 知乎当前仅支持预览和模拟。

### 平台支持矩阵

| 平台 | 预览 | 模拟 | 保存草稿 | 真实发布 | 账号配置 |
|---|:---:|:---:|:---:|:---:|---|
| 公众号 | 支持 | 支持 | 支持 | 支持 | AppID / AppSecret |
| B站 | 支持 | 支持 | 支持 | 支持 | 账号登录 |
| 小红书 | 支持 | 支持 | 联调中 | 联调中 | 待补齐 |
| 知乎 | 支持 | 支持 | 暂不支持 | 暂不支持 | 待上线 |

## 架构概览

- **内容中台**：将正文、素材和元数据标准化为统一 Content IR。
- **平台 Adapter**：负责平台规则、草稿渲染、校验、模拟和发布。
- **AI Agent 编排**：负责内容分析、平台改写、格式检查与建议。
- **发布服务**：保存任务快照，通过 Celery Worker 执行平台发布并记录结果。

新增平台时，优先在 `backend/app/adapters/<platform>/` 中实现 Adapter、Renderer 和 `profile.yaml`，避免把平台规则写入核心服务。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus
- 后端：Python、FastAPI、SQLAlchemy
- 任务队列：Celery、Redis
- 数据库：PostgreSQL
- 平台自动化：Playwright
- AI Agent：OpenAI 兼容 API 与规则回退

## 目录结构

```text
backend/app/api/        FastAPI 路由
backend/app/services/   业务用例与发布任务
backend/app/adapters/   平台渲染、校验与发布 Adapter
backend/app/agents/     AI Agent 编排
frontend/src/           Vue 3 前端工作台
docs/                   架构、API、流程与平台扩展文档
scripts/                本地开发启动脚本
tests/                  后端回归测试
```

完整的文档关系、阅读路径和维护规则见 [文档总览](./docs/README.md)。参与开发前请阅读 [贡献指南](./CONTRIBUTING.md)。

## Docker 部署

Docker Compose 会统一构建并启动完整运行环境，适合首次体验、联调验证和服务器部署：

| 服务 | 作用 | 默认端口 |
|---|---|---:|
| `frontend` | 构建 Vue 前端，并通过 Nginx 提供页面与 API 反向代理 | `80` |
| `backend` | FastAPI 接口、数据库迁移和 Agent 编排 | `8000` |
| `worker` | Celery 发布任务 Worker | 无宿主机端口 |
| `postgres` | 业务数据库 | `5432` |
| `redis` | Celery Broker、任务结果与缓存 | `6379` |

### 1. 准备环境变量

复制 `.env.example` 为 `.env`，至少建议配置以下内容：

```ini
# 用于加密账号凭据，首次部署后请勿更换
CREDENTIAL_ENCRYPTION_KEY=<用 Fernet 生成的密钥>

# 可选：用于文档提取、智能优化和多平台适配
OPENAI_API_KEY=<OpenAI 兼容 API 密钥>
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# 平台需要访问素材时，应填写可公开访问的服务地址
PUBLIC_BASE_URL=http://你的服务地址
```

生成凭据加密密钥：

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

文档导入默认启用 LLM 提取。网络较慢时，导入接口会等待模型响应，最长等待时间可通过 `IMPORT_LLM_TIMEOUT_SECONDS` 调整。Agent 请求超时时间可通过 `AGENT_LLM_TIMEOUT_SECONDS` 调整。

### 2. 构建并启动

在项目根目录执行：

```powershell
docker compose up -d --build
```

首次启动会下载基础镜像、安装依赖并构建前后端，耗时通常比后续启动更长。启动后访问：

- 前端工作台：<http://localhost>
- 后端接口文档：<http://localhost:8000/docs>
- 后端健康检查：<http://localhost:8000/health>

### 3. 查看状态与日志

```powershell
# 查看服务状态
docker compose ps

# 查看全部服务日志
docker compose logs -f

# 仅查看后端和 Worker 日志
docker compose logs -f backend worker
```

`backend` 和 `worker` 启动时都会等待 PostgreSQL 就绪并执行数据库迁移。正常状态下，`backend`、`worker`、`frontend`、`postgres` 和 `redis` 均应处于运行状态。

### 4. 更新与停止

代码或依赖发生变化后，重新构建并启动：

```powershell
docker compose up -d --build
```

仅重建后端和 Worker：

```powershell
docker compose build backend worker
docker compose up -d --force-recreate backend worker
```

停止服务但保留数据：

```powershell
docker compose down
```

素材与日志分别挂载到项目根目录的 `storage/` 和 `logs/`。PostgreSQL 数据保存在 Docker 卷 `postgres_data` 中。请谨慎使用 `docker compose down -v`，该命令会删除数据库卷。

### 5. 常见问题

- **端口占用**：启动前确认本机 `80`、`8000`、`5432` 和 `6379` 端口未被其他程序占用。
- **修改 `.env` 后未生效**：执行 `docker compose up -d --force-recreate backend worker` 重新创建容器。
- **Agent 或文档导入较慢**：检查 `OPENAI_BASE_URL`、模型服务网络和后端日志；文档导入与多平台 Agent 适配会同步等待 LLM 响应。
- **无法真实发布素材**：确认 `PUBLIC_BASE_URL` 是目标平台能够访问的地址，而不是容器内部地址或本地 `blob:` URL。
- **排查 Compose 配置**：执行 `docker compose config` 查看环境变量展开后的配置，但不要将包含密钥的输出公开。

## 本地开发

### 1. 安装依赖

```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 2. 配置环境变量

在项目根目录创建 `.env`，可参考 `.env.example`：

```ini
CREDENTIAL_ENCRYPTION_KEY=<用 Fernet 生成的密钥>
OPENAI_API_KEY=<可选，用于 LLM 增强>
OPENAI_BASE_URL=<可选，OpenAI 兼容接口地址>
OPENAI_MODEL=<可选，模型名称>
PUBLIC_BASE_URL=http://你的服务地址
```

`CREDENTIAL_ENCRYPTION_KEY` 一旦用于保存账号凭据，请勿更换，否则已有凭据将无法解密。

### 3. 启动服务

推荐使用项目脚本：

```powershell
.\scripts\start-containers.ps1
.\scripts\start-backend.ps1
.\scripts\start-worker.ps1
cd frontend
npm run dev
```

需要统一重启后端、Worker 和依赖容器时，可使用 `.\scripts\restart-all.ps1`。

也可以手动启动：

```powershell
docker compose up -d postgres redis
uvicorn backend.app.main:app --reload
celery -A backend.app.tasks.celery_app.celery_app worker --loglevel=info
cd frontend
npm run dev
```

更多脚本说明见 [scripts/README.md](./scripts/README.md)。

## 验证

```powershell
cd frontend
npm run build
cd ..
python -m pytest
python -m compileall backend
git diff --check
```

## 真实发布注意事项

- 真实发布需要 PostgreSQL、Redis 和 Celery Worker 正常运行。
- 公众号发布前，需要将当前服务公网出口 IP 加入微信公众号后台 IP 白名单。
- 公众号正文图片会先上传至微信正文图片接口，再替换为微信 CDN 地址。
- `PUBLIC_BASE_URL` 必须是平台能够访问的地址，本地 `blob:` URL 不能直接用于真实发布。
- 正常停止容器请使用 `docker compose down`；`docker compose down -v` 会删除数据库卷。

## 核心文档

- [架构设计](./docs/architecture.md)
- [API 契约](./docs/api-contract.md)
- [生成预览时序图](./docs/preview-flow.md)
- [发布确认时序图](./docs/publish-flow.md)
- [账号配置时序图](./docs/account-flow.md)
- [平台 Adapter 扩展](./docs/adapter-extension.md)
- [发布字段映射](./docs/publish-field-mapping.md)

## 演示视频

- [百度网盘](https://pan.baidu.com/s/1oQ5dcYsLzLt2VmYnB0rnCw?pwd=fst3)，提取码：`fst3`
- [Bilibili](https://www.bilibili.com/video/BV1rbVQ6HEo5/)
