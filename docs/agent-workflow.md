# AI Agent 工作流

第一阶段提供模拟多 Agent 编排接口，不直接调用真实模型。

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

当前接口执行规则模拟流程：复用内容标准化、平台 Adapter 渲染、格式校验和模拟发布能力，返回每个 Agent 步骤的结构化输出、合规提示和恢复建议。该接口不落库，不调用真实模型，也不会访问真实平台账号。

后续接入 OpenAI Responses API / Agents SDK 时，应把 Adapter 操作封装成工具调用，并开启 tracing 记录每一步决策。
