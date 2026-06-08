# API 契约

当前后端已实现第一阶段最小闭环，并在第二阶段新增公众号、B站真实发布接口；小红书已进入真实发布任务代码路径并接入 myaibot API Adapter，但账号状态、连接测试、状态轮询和真实联调仍需补齐。

## 内容

- `POST /api/v1/content/normalize`：将用户输入标准化为内容 IR，不落库。
- `POST /api/v1/content/adapt`：生成多平台草稿和校验报告，不落库。
- `GET /api/v1/content/platforms`：列出当前支持的平台。
- `POST /api/v1/content/import`：上传 `.md`、`.markdown`、`.txt` 或 `.docx` 文件，解析并提取标题、正文、摘要、标签、内容类型和媒体位置。

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

- `POST /api/v1/previews`：生成平台预览和校验报告。当前预览默认内存计算，不写入 PostgreSQL。
- `PATCH /api/v1/previews/{preview_id}/drafts/{platform}`：校验前端修改后的单个平台草稿，仍不落库。

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

## 素材

- `POST /api/v1/assets`：上传图片、视频或文件到后端本地存储，返回后续发布任务可引用的 `asset_id`。
- `GET /api/v1/assets`：查询本地素材列表。
- `GET /api/v1/assets/{asset_id}`：查询单个素材元信息。
- `GET /api/v1/assets/{asset_id}/download`：下载素材文件，主要用于本地预览和调试。
- `DELETE /api/v1/assets/{asset_id}`：删除素材记录和本地文件。

小红书真实发布依赖素材公网 URL。当前后端本地素材需要通过 `PUBLIC_BASE_URL` 暴露为目标平台可访问的地址；若只使用本地回环地址，myaibot 无法从外网转存素材。

## 发布任务

- `GET /api/v1/publish-tasks`：查询数据库中已有发布任务，默认按创建时间倒序返回；支持 `mode`、`status`、`platform`、`limit` 过滤，用于前端刷新页面后恢复任务看板。
- `POST /api/v1/publish-tasks`：基于预览创建发布任务，支持 `simulate`、`draft`、`publish` 三种模式。请求可以传入 `inline_drafts` 和 `inline_content_ir`，发布任务会保存草稿快照，后续执行不依赖 `previews` 表外键。
- `GET /api/v1/publish-tasks/{task_id}`：查询任务状态。
- `POST /api/v1/publish-tasks/{task_id}/refresh`：刷新真实平台发布状态。当前实现主要覆盖公众号和 B站；小红书二维码与状态轮询仍待接入任务刷新链路。

当前第二阶段中，`mode=draft` 和 `mode=publish` 的目标状态如下：

| 平台 | `simulate` | `draft` / `publish` | 说明 |
|------|------------|---------------------|------|
| `wechat` | 支持 | 支持 | 依赖公众号账号、封面图和正文图片素材上传 |
| `bilibili` | 支持 | 支持 | 依赖 B站登录凭据、视频素材和可选封面图 |
| `xiaohongshu` | 支持 | 代码路径已接入 | 依赖全局 myaibot API Key、素材公网 URL 和素材上下文；账号状态、连接测试和状态轮询仍需补齐 |
| `zhihu` | 支持 | 不支持 | 当前仅做预览和模拟 |

真实发布任务会保存 `account_ids`、`asset_ids`、`platform_options`、`drafts` 和 `content_ir`，并由 Celery worker 执行。

`platform_options` 按平台传入用户确认后的字段：

- `wechat`：`title`、`author`、`digest`、`content_source_url`、`need_open_comment`、`only_fans_can_comment`、`direct_publish`、`cover_asset_id`。
- `bilibili`：`title`、`description`、`tags`、`tid`、`copyright`、`source`、`no_reprint`、`dynamic`、`video_asset_id`、`cover_asset_id`。
- `xiaohongshu`：`title`、`content`、`cover_asset_id`。

更完整的字段回退链和 API 映射见 [发布字段映射](./publish-field-mapping.md)。

## Agent 编排

- `POST /api/v1/agent-runs/preview`：执行第一阶段模拟 Agent 编排，不落库。
- `GET /api/v1/agent-runs/tools`：查询当前后端白名单允许 Agent 调用的内置 MCP 风格工具。
- `POST /api/v1/agent-runs/adapt-preview`：执行工具编排，生成标题/关键词建议、风格改写稿、多平台草稿，并默认保存为 preview。
- `GET /api/v1/agent-runs/llm-health`：检查 LLM API key、模型和端点连通性。
- `GET /api/v1/agent-runs/{run_id}`：查询已经保存的 Agent 工具编排运行详情。

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

旧的 `preview` 编排是规则模拟流程，不调用真实大模型、不调用真实平台、不写入数据库。

`adapt-preview` 新增字段：

- `style_goal`：`professional`、`knowledge`、`social`、`video` 或 `original`。
- `rewrite_strength`：`light`、`medium` 或 `strong`。
- `writing_style`：`default`、`professional`、`concise`、`vivid` 或 `custom`。默认 `default`，表示使用对应平台的默认文字风格；其他预设只控制文字表达风格，不改变 `style_goal` 的平台结构目标。
- `custom_writing_style`：自定义文字风格描述，最多 300 字。仅 `writing_style=custom` 时使用；为空时回退到 `default`。
- `update_title`：是否允许 Agent 修改标题。默认 `false`，未勾选时保留请求中的标题，仅在标题为空时补全。
- `update_tags`：是否允许 Agent 修改关键词。默认 `false`，未勾选时保留请求中的关键词，仅在关键词为空时补全。
- `overwrite_existing_metadata`：兼容旧字段；为 `true` 时等同于同时允许修改标题和关键词。
- `use_llm`：`auto`、`enabled` 或 `disabled`。默认 `auto`，无 `OPENAI_API_KEY` 时自动回退到规则引擎。
- `persist_preview`：是否保存 preview，默认 `true`。

`adapt-preview` 返回：

- `run_id`
- `preview_id`
- `tool_calls`
- `metadata`
- `rewritten_content`
- `content_ir`
- `drafts`
- `validation_report`
- `compliance_report`
- `recommendations`

当前工具编排使用内置工具注册表模拟 MCP 调用规范；当 `use_llm=auto/enabled` 且环境变量中存在可用 `OPENAI_API_KEY` 时，可以尝试 LLM 增强，失败时回退到规则结果。工具编排不自动执行真实发布，真实发布仍需要用户基于 `preview_id` 进入发布确认流程。

## 内容分析

- `POST /api/v1/analysis/content`：对正文进行章节划分、媒体识别、摘要和字数统计。
- `POST /api/v1/analysis/platform-copy`：基于内容分析结果生成多平台结构化文案。
- `POST /api/v1/analysis/full`：一次完成内容分析和多平台文案生成。

当前内容分析链路使用规则引擎，不依赖外部 AI 模型。

## 账号

- `GET /api/v1/accounts`：查询全部平台账号占位状态。
- `GET /api/v1/accounts/{platform}`：查询单个平台账号占位状态。
- `POST /api/v1/accounts/wechat/connect`：登录公众号账号。传入新 `app_secret` 时按 AppID 新建或覆盖历史记录；传入历史 `account_id` 且不传 `app_secret` 时复用已保存密钥。登录成功后该公众号记录会成为当前 active 账号。
- `GET /api/v1/accounts/bilibili/login/captcha`：获取 B站登录所需的 Geetest 初始化参数 `gt`、`challenge`、`token`。
- `POST /api/v1/accounts/bilibili/login/password`：提交账号、密码、captcha token 和极验校验结果，后端加密密码后调用 B站 passport 登录，并加密保存 Cookie 凭据。
- `POST /api/v1/accounts/{platform}/test`：测试账号连接。
- `POST /api/v1/accounts/connections/{account_id}/reveal-secret`：解密并返回已保存的公众号 AppSecret，用于账号管理页主动查看或历史账号回填。
- `DELETE /api/v1/accounts/connections/{account_id}`：断开账号连接。

账号凭据会加密保存到 PostgreSQL。公众号使用 AppID/AppSecret；B站使用 `SESSDATA`、`bili_jct`、`DedeUserID` 等 Cookie 凭据，不保存明文密码。

公众号账号响应包含 `saved_credentials[]` 历史成功登录 AppID 列表，字段包括 `account_id`、`app_id`、`is_active`、`has_secret` 和 `token_expires_at`，不在列表响应中返回 AppSecret。删除 active 公众号记录后不会自动切换到其他历史账号；连接测试和默认真实发布只使用 active 公众号账号。

小红书当前没有独立账号连接接口，发布路径读取全局 `XIAOHONGSHU_API_KEY` 和 `XIAOHONGSHU_API_BASE_URL` 配置；账号页面中的 per-account 状态、连接测试和二维码/状态回显仍属于待补齐能力。

B站密码登录前端集成：先调用 `/bilibili/login/captcha` 获取 `gt`、`challenge`、`token`，再在前端加载 Geetest 组件完成验证。验证成功后，将用户输入的 `username`、`password`，以及 `token`、`challenge`、`validate`、`seccode` 提交到 `/bilibili/login/password`。后端会获取 B站 RSA 公钥并加密密码，不会保存或返回明文密码。如果 B站返回风控或短信验证要求，接口会返回可读错误，用户需要先在浏览器中完成 B站验证后再重试。

## 发布记录

- `GET /api/v1/publications/{publication_id}`：查询真实发布记录。
- `POST /api/v1/publications/{publication_id}/publish`：将平台草稿继续提交发布。第二阶段仅支持公众号草稿，后端会使用草稿记录中的 `media_id` 调用微信提交发布接口。
- `DELETE /api/v1/publications/{publication_id}`：删除平台侧发布内容。第二阶段仅 B站测试稿件支持删除；公众号按平台能力返回不支持。

前端任务看板通过发布任务结果中的 `publication_id` 关联真实发布记录。`mode=draft` 且公众号平台状态为 `draft_created` 时，可以展示“发布草稿”按钮；`mode=publish` 或草稿已经提交后，可以展示“刷新状态”按钮调用任务刷新接口。
