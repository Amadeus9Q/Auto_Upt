# AI Agent 工作流

当前提供两条 Agent 链路：旧的模拟预览编排，以及新的内置 MCP 风格工具编排。工具编排默认使用规则引擎，可在配置 `OPENAI_API_KEY` 后尝试 LLM 增强，并在失败时回退到规则结果。

## Agent 角色

- Content Analyst：分析原文结构、摘要、主题、内容类型和素材需求。
- Platform Stylist：按公众号、知乎、B站、小红书的风格进行改写。
- Format Linter：检查标题长度、图片比例、标签数量、链接限制等。
- Compliance Reviewer：检查 AIGC 标注、版权风险、夸大宣传和低质营销风险。
- Publisher Agent：调用平台 Adapter 执行草稿、模拟或发布。
- Recovery Agent：发布失败后分析日志、截图和平台错误，给出修复建议。

## 第一阶段编排

```text
raw input
  -> Content Analyst
  -> content IR
  -> Platform Stylist for each platform
  -> Adapter render
  -> Format Linter + Compliance Reviewer
  -> simulate publish
  -> preview report
```

后端接口：

- `POST /api/v1/agent-runs/preview`
- `GET /api/v1/agent-runs/tools`
- `POST /api/v1/agent-runs/adapt-preview`
- `GET /api/v1/agent-runs/{run_id}`

旧 `preview` 接口执行规则模拟流程：复用内容标准化、平台 Adapter 渲染、格式校验和模拟发布能力，返回每个 Agent 步骤的结构化输出、合规提示和恢复建议。该接口不落库，不调用真实模型，也不会访问真实平台账号。

## 工具编排

`adapt-preview` 使用白名单工具注册表执行：

```text
raw input
  -> content.normalize
  -> content.analyze
  -> metadata.extract
  -> style.rewrite
  -> platform.render
  -> platform.validate
  -> compliance.review
  -> save preview + agent run
```

工具编排会返回 `tool_calls`，前端可展示每一步工具调用轨迹。它只生成内容建议和 preview，不自动调用真实发布接口。后续接入真实 MCP server 时，应保持工具名称和输入输出结构稳定，将当前内置工具替换为 MCP tool call。

## 前端使用方式

`adapt-preview` 的输出会进入两条前端路径：

1. **平台预览**：`run.drafts` 写入 `preview.drafts`，`PreviewView` 只读取各平台 draft。公众号、B站、知乎、小红书分别渲染标题、摘要、章节标题、正文、标签和素材。
2. **发布确认**：独立配置模式下，`PublishConfirmView` 会用 `preview.drafts.<platform>` 初始化各平台表单字段；统一配置模式下，则优先使用编辑页标题和全局摘要/简介。

Agent 输出不会自动发布。真实发布必须由用户进入发布确认页，确认平台、字段、素材和发布模式后，再创建发布任务。

## 输出字段建议

为了让预览和发布确认都稳定工作，Agent 或平台 renderer 应尽量输出：

- `metadata.title`、`metadata.summary`、`metadata.tags`：用于编辑器建议和内容摘要。
- `rewritten_content.body`：用于“使用优化正文”。
- `drafts.<platform>.title`：平台标题。
- `drafts.<platform>.summary`：摘要、简介或笔记开头。
- `drafts.<platform>.body`：平台正文或视频简介。
- `drafts.<platform>.tags`：平台标签。
- `drafts.<platform>.rich_body` 或 `body_blocks`：结构化章节、段落和素材块。
- `drafts.<platform>.media_slots`：封面、主视频、正文图片、正文音视频等素材槽。

如果 `rich_body` / `body_blocks` 缺失，前端会尝试从纯文本 `body` 中推断章节标题，但无法保证所有格式都能准确识别。
