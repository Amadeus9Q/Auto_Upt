# 生成预览 —— 业务流程图

> 描述从用户输入内容到多平台预览展示的前后端通讯过程。

---

## 泳道图

```mermaid
flowchart TB
    subgraph USER["👤 创作者（EditorView）"]
        U1["输入标题 / 正文 / 标签"]
        U2["选择目标平台"]
        U3["上传素材"]
        U4["点击「生成预览」"]
        U5["查看各平台预览<br/>切换 Tab + 校验提示"]
    end

    subgraph FE["🖥️ 前端"]
        F1["汇总为 ContentPayload"]
        F2["POST /api/v1/previews"]
        F3["接收 PreviewResponse<br/>按平台拆解 draft"]
        F4["PreviewView 渲染各平台组件"]
    end

    subgraph BE["⚙️ 后端（FastAPI + PreviewService）"]
        B1["标准化内容 → content_ir<br/>LLM 补全标题/标签/摘要"]
        B2["内容分析<br/>章节划分 / 媒体识别"]
        B3["逐平台 Adapter.render()<br/>content_ir → 平台草稿"]
        B4["逐平台 Adapter.validate()<br/>格式校验 → 警告/错误"]
        B5["汇总返回<br/>preview_id + drafts + validation_report"]
    end

    subgraph ADP["🎨 平台 Adapter"]
        D1["加载平台规则 profile.yaml"]
        D2["渲染 draft：标题/正文/富文本/媒体槽位"]
        D3["校验：字数/图片/标签/链接"]
    end

    U1 & U2 & U3 --> U4
    U4 --> F1
    F1 --> F2
    F2 -->|"HTTP POST"| B1
    B1 --> B2
    B2 --> B3
    B3 --> D1 --> D2 --> D3
    D3 --> B4
    B4 --> B5
    B5 -->|"PreviewResponse"| F3
    F3 --> F4
    F4 --> U5

    style USER fill:#e3f2fd,stroke:#1565c0
    style FE fill:#e8f5e9,stroke:#2e7d32
    style BE fill:#f3e5f5,stroke:#7b1fa2
    style ADP fill:#fce4ec,stroke:#c62828
```

---

## 步骤详解

### Step 1：前端构建请求

创作者填写标题/正文/标签，选择目标平台，上传素材后点击「生成预览」。前端汇总为 `ContentPayload` 发送 `POST /api/v1/previews`。

### Step 2：后端内容标准化

后端将用户输入标准化为**内容 IR**（统一中间表示）：
- 标题为空时，LLM 从正文推断（LLM 不可用时回退到正文首行）
- 标签为空时，LLM 提取关键词（规则兜底）
- 分析章节结构、媒体素材位置、字数统计

### Step 3：逐平台渲染草稿

对每个选中平台，调用 `Adapter.render(content_ir)` 将内容 IR 转为平台草稿：

| 平台 | 渲染输出 |
|------|---------|
| 公众号 | 富文本 HTML + 结构化渲染块 + 封面/素材槽位 |
| B站 | 视频标题 + 简介 + 标签 + 分区 |
| 知乎 | 文章块格式（结论/标题/引用/图片） |
| 小红书 | 笔记标题 + 正文 + 话题标签 + 图片槽位 |

然后执行 `Adapter.validate(draft)` 校验格式，返回错误/警告/提示。

### Step 4：返回前端展示

后端返回 `PreviewResponse`（含 `preview_id`、`drafts`、`validation_report`），前端按平台 Tab 渲染预览组件——公众号手机窗格、B站播放器样式、知乎文章样式、小红书笔记窗格。

---

## 关键设计决策

| 决策 | 原因 |
|------|------|
| 预览不落库 | 临时计算产物，避免数据一致性问题 |
| LLM 增强 + 规则回退 | 无 API Key 时预览仍可用 |
| 平台 Adapter 解耦 | 新增平台只需加 adapter + profile.yaml |
| 统一 IR 中转 | 各平台 Adapter 基于同一份标准化内容渲染 |

---

> **相关文档**：[架构设计](./architecture.md) · [API 契约](./api-contract.md) · [发布确认流程图](./publish-flow.md) · [账号登录流程图](./account-flow.md)
