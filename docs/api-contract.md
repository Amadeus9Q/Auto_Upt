# API 契约草案

当前 API 文件只放接口占位，不实现完整逻辑。

## 内容

- `POST /api/v1/content/normalize`：将用户输入标准化为内容 IR。
- `POST /api/v1/content/adapt`：生成多平台草稿。

## 预览

- `POST /api/v1/previews`：生成平台预览和校验报告。
- `GET /api/v1/previews/{preview_id}`：查询预览详情。

## 发布任务

- `POST /api/v1/publish-tasks`：创建草稿、模拟或发布任务。
- `GET /api/v1/publish-tasks/{task_id}`：查询任务状态。
- `POST /api/v1/publish-tasks/{task_id}/confirm`：二次确认后才允许真实发布。

## 账号

- `GET /api/v1/accounts`：列出平台账号。
- `POST /api/v1/accounts`：创建账号授权占位记录。
- `POST /api/v1/accounts/{account_id}/verify`：验证账号授权状态。
