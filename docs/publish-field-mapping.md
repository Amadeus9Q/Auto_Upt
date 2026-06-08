# 发布确认 — 字段来源与 API 映射

> 本文档描述从 Agent 预览输出 → 发布确认表单 → 前端提交合并 → 后端平台 Adapter → 平台 API 的完整数据链路。

---

## 1. 全局字段流向图

```mermaid
flowchart TB
    subgraph FE["前端编辑区"]
        E1["统一内容字段<br/>title / content / tags / selected_platforms"]
        E2["素材库<br/>images / videos / audios / cover_image"]
        E3["正文结构<br/>content_blocks / asset markers"]
    end

    subgraph AGENT_IN["Agent 输入"]
        A1["buildContentPayload()<br/>标题、正文、标签、素材、平台"]
        A2["buildAgentMetadataPayload()<br/>是否更新标题 / 标签 / 正文"]
    end

    subgraph AGENT_OUT["Agent 输出"]
        O1["metadata<br/>title / summary / tags"]
        O2["rewritten_content<br/>优化后的正文"]
        O3["drafts.wechat<br/>title / summary / body / wechat_html / tags / rich_body"]
        O4["drafts.bilibili<br/>title / body / tags / media_slots"]
        O5["drafts.zhihu<br/>title / summary / body / tags / rich_body"]
        O6["drafts.xiaohongshu<br/>title / summary / body / tags / media_slots"]
        O7["validation_report<br/>各平台提示"]
    end

    subgraph PREVIEW["平台预览"]
        P1["PreviewView<br/>读取 preview.drafts"]
        P2["公众号预览<br/>标题、摘要、章节、正文、封面"]
        P3["B站预览<br/>标题、简介、标签、视频、封面、章节"]
        P4["知乎预览<br/>标题、摘要、章节、正文、图片"]
        P5["小红书预览<br/>标题、摘要、正文、章节、图片轮播、话题"]
    end

    subgraph CONFIRM["发布确认页"]
        C1["统一配置<br/>globalTitle / globalSummary"]
        C2["独立配置<br/>publishForms.<platform>"]
        C3["平台专属字段<br/>公众号作者/评论<br/>B站标签/分类<br/>小红书标题/正文"]
    end

    subgraph PAYLOAD["前端提交"]
        B1["buildPlatformOptions()<br/>生成 platform_options"]
        B2["buildPublishTaskPayload()<br/>生成 asset_ids / content_blocks / inline_drafts"]
        B3["POST /api/v1/publish-tasks"]
    end

    subgraph BACKEND["后端发布任务"]
        S1["PublishService<br/>读取 preview 或 inline_drafts"]
        S2["Adapter.publish()<br/>options + draft + assets"]
    end

    subgraph API["平台 API 输入来源"]
        W1["公众号 API<br/>title: options.title 或 draft.title<br/>digest: options.digest 或 draft.summary<br/>content: draft.wechat_html / draft.body<br/>thumb_media_id: cover_asset_id<br/>author/comment: options"]
        BILI1["B站 API<br/>title: options.title 或 draft.title<br/>description: options.description 或 draft.body<br/>tags: options.tags 或 draft.tags<br/>video/cover: asset_ids + options"]
        XHS1["小红书 API<br/>title: options.title 或 draft.title<br/>content: options.content 或 draft.body<br/>images/video/cover: asset_ids + options"]
        ZH1["知乎<br/>有平台草稿预览和模拟发布<br/>不进入真实发布 API"]
    end

    E1 --> A1
    E2 --> A1
    E3 --> A1
    A2 --> A1
    A1 --> O1
    A1 --> O2
    A1 --> O3
    A1 --> O4
    A1 --> O5
    A1 --> O6
    A1 --> O7

    O3 --> P1
    O4 --> P1
    O5 --> P1
    O6 --> P1
    P1 --> P2
    P1 --> P3
    P1 --> P4
    P1 --> P5

    E1 --> C1
    O3 --> C2
    O4 --> C2
    O6 --> C2
    C1 --> C3
    C2 --> C3

    C3 --> B1
    E2 --> B2
    E3 --> B2
    O3 --> B2
    O4 --> B2
    O6 --> B2
    B1 --> B2
    B2 --> B3

    B3 --> S1
    S1 --> S2
    S2 --> W1
    S2 --> BILI1
    S2 --> XHS1
    O5 --> ZH1
```

- **前端编辑区** 是 Agent 和发布任务的共同源头：标题、正文、标签、素材、正文中的素材引用都会进入 `buildContentPayload()`。
- **Agent 输出** 分成两类用途：一类用于平台预览（`preview.drafts.<platform>`），另一类作为发布确认页独立配置模式下的默认值。
- **平台预览** 只读取 `preview.drafts`，不会直接读取统一编辑区正文；标题、摘要、章节标题、正文、图片等展示效果由各平台 draft 决定。
- **发布确认页** 决定最终提交字段：统一配置优先用 `globalTitle/globalSummary`，独立配置优先用各平台 `publishForms`。
- **平台 API 输入** 来自两部分合并：`platform_options` 提供用户确认后的字段，`drafts.<platform>` 提供 Agent 生成的平台正文和兜底字段，`asset_ids` 提供封面、图片、视频等素材。
- **知乎** 当前生成 `drafts.zhihu` 供预览和模拟发布使用，但不进入真实发布 API。

---

## 2. Agent 输出结构

Agent 或平台 renderer 为每个平台生成 `drafts.<platform>` 对象。各平台都可以包含以下通用字段：

- `title`：平台标题。
- `summary`：摘要、简介或平台推荐开头。
- `body`：平台正文、回答正文或视频简介。
- `tags`：平台标签。
- `rich_body` 或 `body_blocks`：结构化章节、段落和素材块。
- `media_slots`：封面、主视频、正文图片、正文音视频等素材槽。

平台专用字段如下：

| 平台 | 字段 | 类型 | 说明 |
|------|------|------|------|
| **公众号** | `title` | `string` | 文章标题 |
| | `summary` | `string` | 文章摘要 |
| | `body` | `string` | HTML 正文 |
| | `wechat_html` | `string` | 公众号专用格式化 HTML |
| **B站** | `title` | `string` | 视频标题 |
| | `body` | `string` | 视频简介/描述 |
| | `tags` | `string[]` | 标签列表 |
| **小红书** | `title` | `string` | 笔记标题 |
| | `body` | `string` | 笔记正文（纯文本） |
| **知乎** | `title` | `string` | 回答或文章标题 |
| | `summary` | `string` | 摘要 |
| | `body` | `string` | 回答或文章正文 |
| | `tags` | `string[]` | 话题或关键词 |

---

## 3. 发布确认表单

### 3.1 统一配置模式 (`PublishConfirmView`)

独立全局字段（不与 `wechat` 耦合），写入时**同步至所有选定平台**。

| 全局字段 | 初始值来源 | 同步至 |
|---------|----------|--------|
| `globalTitle` | `editorTitle` prop（编辑页标题） | `wechat.title`、`bilibili.title`、`xiaohongshu.title` |
| `globalSummary` | `""`（空字符串，由用户按需填写） | `wechat.summary`、`bilibili.description`、`xiaohongshu.content` |

**模式切换行为**：

| 切换方向 | 行为 |
|---------|------|
| 统一 → 独立 | 各平台表单从 **Agent 草稿** 初始化（`populateFromAgent`），不继承全局值 |
| 独立 → 统一 | `globalTitle`/`globalSummary` **保持不变**，重新同步到所有平台；不反向拉取 `wechat.title` |

平台唯一字段（仅勾选对应平台时显示）：

| 平台 | 表单字段 | 对应变量 |
|------|---------|----------|
| 公众号 | 作者 | `wechat.author` |
| | 原文链接 | `wechat.contentSourceUrl` |
| | 开启评论 | `wechat.needOpenComment` |
| | 仅粉丝可评论 | `wechat.onlyFansCanComment` |
| B站 | 标签（逗号分隔） | `bilibili.tags` |
| | 分类 | `bilibili.category` |
| 小红书 | — | 无额外字段，title/content 由全局同步 |

### 3.2 独立配置模式 (`PublishFormView`)

每个平台有独立 Tab，直接编辑 `publishForms.<platform>.*`：

| 平台 | Tab 字段 | 限制 |
|------|---------|------|
| 公众号 | 标题、摘要、作者、原文链接、评论设置、发布方式 | title≤64字, summary≤120字 |
| B站 | 仅显示封面/视频素材状态 | — |
| 小红书 | 标题、正文 | title≤20字符, content≤1000字符 |
| 知乎 | 无真实发布表单（仅预览和模拟） | — |

---

## 4. 前端提交合并 (`App.vue` → `buildPlatformOptions`)

`PublishConfirmView.submit()` 将 `useUnifiedSettings` 通过 emit 传递到 `App.submitPublish()` → `buildPublishTaskPayload()` → `buildPlatformOptions(platforms, unified)`。

### 4.1 统一模式（`unified=true`）

跳过 Agent 回退，全局标题/简介已同步写入各平台表单字段。

| 平台 | 最终字段 | 回退链 |
|------|---------|--------|
| 公众号 | `title` | ① `wechat.title` → ② `title` (编辑页标题) |
| | `digest` | ① `wechat.summary`（无回退） |
| B站 | `title` | ① `bilibili.title` → ② `title` (编辑页标题) |
| | `description` | ① `bilibili.description`（无回退） |
| 小红书 | `title` | ① `xiaohongshu.title` → ② `title` (编辑页标题) |
| | `content` | ① `xiaohongshu.content`（无回退） |

### 4.2 独立模式（`unified=false`）

保留三级回退链：**表单值 → Agent 输出 → 全局/编辑器值**。

**公众号**

| 最终字段 | 回退链 |
|---------|--------|
| `title` | ① `wechat.title` → ② `drafts.wechat.title` → ③ `title` (编辑页标题) |
| `author` | ① `wechat.author`（无回退） |
| `digest` | ① `wechat.summary` → ② `drafts.wechat.summary` → ③ `""` |
| `content_source_url` | ① `wechat.contentSourceUrl`（无回退） |
| `need_open_comment` | ① `wechat.needOpenComment`（布尔值） |
| `only_fans_can_comment` | ① `needOpenComment && wechat.onlyFansCanComment` |
| `direct_publish` | ① `wechat.directPublish`（与 `selectedMode` 联动） |

**B站**

| 最终字段 | 回退链 |
|---------|--------|
| `title` | ① `bilibili.title` → ② `drafts.bilibili.title` → ③ `title` (编辑页标题) |
| `description` | ① `bilibili.description` → ② `drafts.bilibili.body` → ③ `content` (编辑器正文) |
| `tags` | ① `bilibili.tags` 逗号拆分 → ② `drafts.bilibili.tags` → ③ `[]` |
| `tid` | 固定 `201` (科技分类) |
| `copyright` | 固定 `1` (自制) |
| `source` | 固定 `""` |
| `no_reprint` | 固定 `true` |
| `dynamic` | 固定 `""` |

**小红书**

| 最终字段 | 回退链 |
|---------|--------|
| `title` | ① `xiaohongshu.title` → ② `drafts.xiaohongshu.title` → ③ `title` (编辑页标题) |
| `content` | ① `xiaohongshu.content` → ② `drafts.xiaohongshu.body` → ③ `""` |

> ⚠️ 小红书不回退到公众号字段。Agent 输出的 `drafts.xiaohongshu` 是内容来源。

### 4.3 素材映射 (`buildPublishTaskPayload`)

| 平台 | 素材要求 | 对应 `asset_ids` / `platform_options` |
|------|---------|--------------------------------------|
| 公众号 | 封面图 + 正文图片 | `asset_ids.wechat`，`platform_options.wechat.cover_asset_id` |
| B站 | 视频 + 封面图 | `asset_ids.bilibili`，`platform_options.bilibili.video_asset_id`、`cover_asset_id` |
| 小红书 | 封面图 + 图片/视频 | `asset_ids.xiaohongshu`，`platform_options.xiaohongshu.cover_asset_id` |

小红书真实发布需要 myaibot 可访问的公网素材 URL。当前后端素材下载接口为 `/api/v1/assets/{asset_id}/download`，生产或演示环境应确保 `PUBLIC_BASE_URL` 指向外网可访问地址。

---

## 5. 后端 Adapter → 平台 API 映射

### 5.1 公众号 → 微信公众平台 API

**API 端点**：
- `POST /cgi-bin/material/add_material` — 上传封面图 (永久素材)
- `POST /cgi-bin/media/uploadimg` — 上传正文图片
- `POST /cgi-bin/draft/add` — 创建草稿
- `POST /cgi-bin/freepublish/submit` — 发布草稿

**Adapter 字段 → API 字段**：

| Adapter 输入 (`options.*`) | 回退 (`draft.*`) | API 字段 (`article.*`) | 说明 |
|---|---|---|---|
| `options.title` | `draft.title` | `title` | 文章标题 |
| `options.author` | — | `author` | 作者名 |
| `options.digest` | `draft.summary` | `digest` | 摘要 (≤120字) |
| (正文图片替换后) | `draft.wechat_html` | `content` | HTML 正文 |
| `options.content_source_url` | — | `content_source_url` | 原文链接 |
| (封面素材 ID) | — | `thumb_media_id` | 封面图 media_id |
| `options.need_open_comment` | — | `need_open_comment` | 0/1 |
| `options.only_fans_can_comment` | — | `only_fans_can_comment` | 0/1 |

### 5.2 B站 → B站投稿 API

**API 端点**：B站会员中心 `POST` 投稿接口（Cookie 鉴权）

**Adapter 字段 → API 字段**：

| Adapter 输入 (`options.*`) | 回退 (`draft.*`) | API 字段 (`payload.*`) | 说明 |
|---|---|---|---|
| `options.title` | `draft.title` | `title` | 视频标题 |
| `options.description` | `draft.body` | `description` | 视频简介 |
| `options.tags` | `draft.tags` | `tags` | 标签列表 |
| (上传后) | — | `video_id` | 视频投稿 ID |
| (上传后) | — | `cover` | 封面信息 |
| `options.tid` | — | `tid` | 分区 ID (默认 201) |
| `options.copyright` | — | `copyright` | 1=自制 2=转载 |
| `options.source` | — | `source` | 转载来源 |
| `options.no_reprint` | — | `no_reprint` | 0/1 禁止转载 |
| `options.dynamic` | — | `dynamic` | 分享动态文案 |

### 5.3 小红书 → myaibot.vip API

**API 端点**：
- `POST /api/rednote/publish-with-upload` — 提交笔记（自动转存图片/视频）
- `POST /api/rednote/{id}/status` — 查询发布状态

**Adapter 字段 → API 字段**：

| Adapter 输入 (`options.*`) | 回退 (`draft.*`) | API 字段 (`payload.*`) | 说明 |
|---|---|---|---|
| `options.title` | `draft.title` | `title` | 笔记标题 (≤20字符) |
| `options.content` | `draft.body` | `content` | 笔记正文 (≤1000字符) |
| (收集图片 URL) | — | `images[]` | 图片链接数组 (图文笔记) |
| (收集视频 URL) | — | `video` | 视频链接 (视频笔记) |
| (收集封面 URL) | — | `cover` | 封面图链接 |
| (自动判定) | — | `type` | `"normal"` (图文) / `"video"` (视频) |
| (配置) | — | `api_key` | myaibot API 密钥 |

> **发布流程**：提交后返回二维码 → 用户扫码在手机端完成发布。myaibot 支持 `uploading → pending → submitted` 状态查询，但当前后端任务刷新链路尚未完整接入小红书轮询展示。

---

## 6. 平台限制速查

| 限制项 | 公众号 | B站 | 小红书 |
|-------|--------|-----|--------|
| 标题最大长度 | 200 字 | 200 字 | **20 字符** (中文×1, 英文/数字×0.5) |
| 正文最大长度 | 无限制 | 无限制 | **1000 字符** |
| 摘要/简介 | 120 字 | — | — |
| 标签数 | 20 | 20 | 20 |
| 封面图 | 必填 | 可选 | **必填** |
| 图片 | 正文内插图 | — | ≤18 张, ≤32MB/张, PNG/JPG/WebP |
| 视频 | — | 必填 | ≤20GB, ≤60min |
| 鉴权方式 | OAuth (app_id+app_secret) | Cookie (SESSDATA+bili_jct) | API Key |
| 发布模式 | simulate / draft / publish | simulate / draft / publish | simulate / draft / publish（代码路径已接入，联调待补齐） |

知乎当前支持平台草稿预览和模拟发布，不进入真实发布 API。

---

## 7. 发布确认页前端字段速查

### 统一配置模式

```
┌─ 全局标题 ─────────────────────────────────────┐
│  → wechat.title, bilibili.title, xiaohongshu.title │
└────────────────────────────────────────────────┘
┌─ 全局摘要/简介 ────────────────────────────────┐
│  → wechat.summary, bilibili.description,        │
│    xiaohongshu.content                          │
└────────────────────────────────────────────────┘
┌─ 发布方式 (任一可发布平台选中时显示) ──────────┐
│  ○ 模拟  ○ 保存草稿  ○ 真实发布                 │
└────────────────────────────────────────────────┘
┌─ 公众号 (勾选时显示) ──────────────────────────┐
│  作者、原文链接、评论设置                        │
└────────────────────────────────────────────────┘
┌─ B站 (勾选时显示) ─────────────────────────────┐
│  标签(逗号分隔)、分类                            │
└────────────────────────────────────────────────┘
```

### 独立配置模式

```
┌─ Tabs ─────────────────────────────────────────┐
│  [公众号] [B站] [小红书] [知乎]                  │
│                                                 │
│  公众号 Tab: 标题、摘要、作者、原文链接、         │
│             评论设置、发布方式                    │
│  B站 Tab: 封面/视频素材状态                      │
│  小红书 Tab: 标题(20字)、正文(1000字)            │
│  知乎 Tab: 仅预览和模拟，无真实发布表单          │
└────────────────────────────────────────────────┘
```
