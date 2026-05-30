# API 契约

当前后端已实现第一阶段最小闭环：内容标准化、多平台草稿适配、预览落库和模拟发布任务。

## 内容

- `POST /api/v1/content/normalize`：将用户输入标准化为内容 IR，不落库。
- `POST /api/v1/content/adapt`：生成多平台草稿和校验报告，不落库。
- `GET /api/v1/content/platforms`：列出当前支持的平台。

请求字段：

- `title?`
- `body`
- `content_type`：`article`、`video` 或 `mixed`，默认 `article`
- `tags[]`
- `assets[]`
- `platforms[]?`：`wechat`、`zhihu`、`xiaohongshu`、`bilibili`

## 预览

- `POST /api/v1/previews`：生成平台预览和校验报告，并保存到 PostgreSQL。
- `GET /api/v1/previews/{preview_id}`：查询预览详情。

预览响应包含：

- `preview_id`
- `content_ir`
- `drafts`
- `validation_report`
- `created_at`

## 发布任务

- `POST /api/v1/publish-tasks`：基于预览创建模拟发布任务。
- `GET /api/v1/publish-tasks/{task_id}`：查询任务状态。

当前 MVP 只支持 `mode=simulate`。`draft` 和 `publish` 会返回 400，真实发布在后续阶段接入。

## Agent 编排

- `POST /api/v1/agent-runs/preview`：执行第一阶段模拟 Agent 编排，不落库。

请求字段：

- `title?`
- `body`
- `content_type`：`article`、`video` 或 `mixed`，默认 `article`
- `tags[]`
- `assets[]`
- `platforms[]?`：为空时覆盖全部已支持平台
- `include_simulation`：是否执行模拟发布步骤，默认 `true`

响应包含：

- `run_id`
- `status`
- `mode`
- `platforms`
- `steps`
- `content_ir`
- `drafts`
- `validation_report`
- `compliance_report`
- `simulation_results`
- `recommendations`
- `created_at`

当前 Agent 编排是规则模拟流程，不调用真实大模型、不调用真实平台、不写入数据库。

## 账号

- `GET /api/v1/accounts`：查询全部平台账号占位状态。
- `GET /api/v1/accounts/{platform}`：查询单个平台账号占位状态。

账号接口当前只为前端账号页面提供占位数据，统一返回 `not_configured` 状态。真实账号授权、校验和发布确认在后续阶段接入。
