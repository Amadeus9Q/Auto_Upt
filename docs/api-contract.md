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

- `POST /api/v1/publish-tasks`：基于预览创建模拟发布或真实发布任务。
- `GET /api/v1/publish-tasks/{task_id}`：查询任务状态。
- `POST /api/v1/publish-tasks/{task_id}/refresh`：刷新真实平台发布状态。

发布请求字段：

- `preview_id`
- `mode`：`simulate`、`draft` 或 `publish`
- `platforms[]?`
- `account_ids?`：真实发布账号 ID 映射
- `asset_ids?`：真实发布素材 ID 映射
- `platform_options?`：平台发布参数

当前真实发布只支持 `wechat` 和 `bilibili`。知乎和小红书仍保持模拟发布或后续浏览器辅助发布。

## 素材

- `POST /api/v1/assets`：上传图片、封面、视频等本地素材。
- `GET /api/v1/assets`：查询素材列表。
- `GET /api/v1/assets/{asset_id}`：查询素材详情。
- `GET /api/v1/assets/{asset_id}/download`：下载素材文件。
- `DELETE /api/v1/assets/{asset_id}`：删除素材记录和本地文件。

真实发布任务通过 `asset_id` 引用素材，不直接接收服务器文件路径。

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
- `DELETE /api/v1/publications/{publication_id}`：删除平台侧发布内容。第二阶段仅 B站支持删除测试稿件，公众号按平台能力返回不支持。
