# 平台扩展设计

新增平台时，只需要在 `backend/app/adapters/<platform>/` 下新增插件目录。

```text
backend/app/adapters/<platform>/
  adapter.py
  renderer.py
  profile.yaml
```

## 必须实现的接口

平台适配器需要继承 `PlatformAdapter`，并实现以下方法：

- `capabilities()`：声明支持的内容类型、发布模式、鉴权方式、限制能力。
- `render(content, profile)`：把统一内容 IR 转为平台草稿。
- `validate(draft)`：返回标题、正文、图片、标签、链接等校验问题。
- `publish(draft, account, mode)`：执行草稿、模拟或真实发布。真实发布时 `account` 不只是账号凭据，也会携带素材和前端确认字段。
- `simulate(draft)`：生成预览、截图和模拟报告。

## 发布上下文约定

真实发布任务由 `PublishService` 构建 `account` 上下文后传入 Adapter：

```python
{
    "account_id": "...",
    "credentials": {...},
    "assets": [LocalAsset(...), ...],
    "options": {...},
}
```

字段含义：

- `credentials`：账号凭据。公众号来自 AppID/AppSecret；B站来自 Cookie；小红书当前依赖全局 API Key。
- `assets`：从 `asset_ids.<platform>` 和 draft 中自动发现的素材 ID 加载而来。
- `options`：前端发布确认页合并后的 `platform_options.<platform>`。

Adapter 应优先使用 `options` 中用户确认后的字段；当字段为空时，再回退到 `draft` 中由 Agent 或平台 renderer 生成的字段。

## 当前平台发布输入

| 平台 | Adapter 输入重点 | 素材要求 | 状态 |
|------|------------------|----------|------|
| 公众号 | `options.title`、`options.digest`、`draft.wechat_html`、评论设置 | 封面图、正文图片 | 已接入真实发布 |
| B站 | `options.title`、`options.description`、`options.tags`、分区/版权设置 | 主视频、可选封面 | 已接入真实发布 |
| 小红书 | `options.title`、`options.content`、图片/视频公网 URL | 至少一张图片或一个视频，建议封面 | Adapter 已接入，账号入口和联调待补齐 |
| 知乎 | `draft.title`、`draft.body`、`draft.tags` | 仅预览 | 暂不真实发布 |

## profile.yaml 约定

`profile.yaml` 保存平台规则，不把规则硬编码在核心流程里。

需要包含：

- `platform`
- `display_name`
- `content_types`
- `limits`
- `publish_modes`
- `auth`
- `style`
- `assets`

核心流程只读取平台 profile 和 Adapter 能力，不关心平台内部实现。

## 前端预览字段建议

为了让平台预览稳定渲染，Adapter 或 renderer 生成 draft 时建议包含：

- `title`：平台标题。
- `summary`：摘要、简介或平台推荐开头。
- `body`：平台正文或简介。
- `tags`：平台标签。
- `rich_body` 或 `body_blocks`：结构化正文块，推荐包含 `heading`、`paragraph`、`image`、`video`、`audio`。
- `media_slots`：平台素材槽，例如 `cover`、`main_video`、`body_images`、`body_videos`、`body_audios`。
- `cover_image`：封面图，前端手机窗格和 B站播放器会优先使用。

如果只返回纯文本 `body`，前端会尝试用 Markdown 标题、编号标题等规则解析章节标题，但稳定性不如结构化字段。
