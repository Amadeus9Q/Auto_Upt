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

- `GET /api/v1/publish-tasks`：查询数据库中已有发布任务，默认按创建时间倒序返回；支持 `mode`、`status`、`platform`、`limit` 过滤，用于前端刷新页面后恢复任务看板。
- `POST /api/v1/publish-tasks`：基于预览创建发布任务，支持 `simulate`、`draft`、`publish` 三种模式。
- `GET /api/v1/publish-tasks/{task_id}`：查询任务状态。
- `POST /api/v1/publish-tasks/{task_id}/refresh`：刷新真实平台发布状态。

当前第二阶段中，`mode=draft` 和 `mode=publish` 仅允许 `wechat`、`bilibili`。真实发布任务会保存 `account_ids`、`asset_ids`、`platform_options`，并由 Celery worker 执行。`zhihu` 和 `xiaohongshu` 在真实发布模式下返回不支持状态，后续浏览器辅助发布阶段再接入。

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
- `POST /api/v1/accounts/wechat/connect`：保存公众号 AppID/AppSecret，并可测试 access token。
- `GET /api/v1/accounts/bilibili/login/captcha`：获取 B站登录所需的 Geetest 初始化参数 `gt`、`challenge`、`token`。
- `POST /api/v1/accounts/bilibili/login/password`：提交账号、密码、captcha token 和极验校验结果，后端加密密码后调用 B站 passport 登录，并加密保存 Cookie 凭据。
- `POST /api/v1/accounts/{platform}/test`：测试账号连接。
- `DELETE /api/v1/accounts/connections/{account_id}`：断开账号连接。

账号凭据会加密保存到 PostgreSQL。公众号使用 AppID/AppSecret；B站使用 `SESSDATA`、`bili_jct`、`DedeUserID` 等 Cookie 凭据，不保存明文密码。

B站密码登录前端集成：先调用 `/bilibili/login/captcha` 获取 `gt`、`challenge`、`token`，再在前端加载 Geetest 组件完成验证。验证成功后，将用户输入的 `username`、`password`，以及 `token`、`challenge`、`validate`、`seccode` 提交到 `/bilibili/login/password`。后端会获取 B站 RSA 公钥并加密密码，不会保存或返回明文密码。如果 B站返回风控或短信验证要求，接口会返回可读错误，用户需要先在浏览器中完成 B站验证后再重试。

## 发布记录

- `GET /api/v1/publications/{publication_id}`：查询真实发布记录。
- `POST /api/v1/publications/{publication_id}/publish`：将平台草稿继续提交发布。第二阶段仅支持公众号草稿，后端会使用草稿记录中的 `media_id` 调用微信提交发布接口。
- `DELETE /api/v1/publications/{publication_id}`：删除平台侧发布内容。第二阶段仅 B站测试稿件支持删除；公众号按平台能力返回不支持。

前端任务看板通过发布任务结果中的 `publication_id` 关联真实发布记录。`mode=draft` 且公众号平台状态为 `draft_created` 时，可以展示“发布草稿”按钮；`mode=publish` 或草稿已经提交后，可以展示“刷新状态”按钮调用任务刷新接口。
