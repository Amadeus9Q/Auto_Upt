# API 契约

当前后端已实现第一阶段最小闭环，并在第二阶段新增公众号和 B站真实发布接口。

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
- `content_blocks[]?`：结构化正文块，按顺序描述文本和素材引用，例如 `{ type: "asset", asset_id, asset_kind }`。
- `cover_asset_id?`：封面图素材 ID。为空时后端按素材用途自动选择。
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

平台草稿可以包含：

- `body_blocks`：按平台渲染后的正文块，用于前端在预览中插入图片、视频、音频。
- `media_slots`：平台素材槽位，例如 `cover`、`main_video`、`body_images`、`body_videos`、`body_audios`。
- `rich_body`：公众号等富文本预览使用的结构化渲染块。

## 发布任务

- `POST /api/v1/publish-tasks`：基于预览创建发布任务，支持 `simulate`、`draft`、`publish` 三种模式。
- `GET /api/v1/publish-tasks/{task_id}`：查询任务状态。
- `POST /api/v1/publish-tasks/{task_id}/refresh`：刷新真实平台发布状态。

当前第二阶段前端联调中，`mode=draft` 和 `mode=publish` 仅允许 `wechat`、`bilibili`，后端返回模拟任务结果，不调用真实平台接口。`zhihu` 和 `xiaohongshu` 在真实发布模式下返回不支持状态，后续浏览器辅助发布阶段再接入。

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

- `GET /api/v1/accounts`：查询全部平台账号状态，直接返回账号状态数组。
- `GET /api/v1/accounts/{platform}`：查询单个平台账号状态。
- `POST /api/v1/accounts/wechat/connect`：保存公众号 AppID / AppSecret 配置，返回公众号连接状态。
- `GET /api/v1/accounts/bilibili/oauth/start`：启动 B站 OAuth 授权流程；当前返回模拟授权结果。
- `GET /api/v1/accounts/bilibili/oauth/callback`：接收 B站 OAuth 回调；当前记录模拟授权状态。
- `POST /api/v1/accounts/{platform}/test`：测试平台账号连接状态。
- `DELETE /api/v1/accounts/{platform}`：断开平台账号连接。

账号接口当前用于前端账号管理页联调，公众号和 B站返回进程内模拟连接状态；知乎、小红书继续展示“第三阶段浏览器辅助发布接入”。真实凭据加密落库、Token 刷新和平台联调在后续后端任务中接入。
