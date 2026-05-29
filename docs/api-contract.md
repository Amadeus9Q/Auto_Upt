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

## 账号

账号接口暂未实现。真实账号授权、校验和发布确认在后续阶段接入。
