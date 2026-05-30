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

当前接口执行规则模拟流程：复用内容标准化、平台 Adapter 渲染、格式校验和模拟发布能力，返回每个 Agent 步骤的结构化输出、合规提示和恢复建议。该接口不落库，不调用真实模型，也不会访问真实平台账号。

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
