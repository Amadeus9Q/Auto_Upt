# 系统架构设计

## 总体思路

项目采用“内容中台 + 平台适配器 + AI Agent 发布助理”。

```mermaid
flowchart LR
    A["创作者输入 Markdown/富文本/视频信息"] --> B["内容标准化 IR"]
    B --> C["AI Agent 编排层"]
    C --> D["平台适配器"]
    D --> E["公众号 Adapter"]
    D --> F["B站 Adapter"]
    D --> G["知乎 Adapter"]
    D --> H["小红书 Adapter"]
    E --> I["官方 API / 草稿"]
    F --> J["官方 API / biliup / 浏览器"]
    G --> K["浏览器辅助 / 模拟"]
    H --> L["myaibot API / 模拟"]
    C --> M["预览、校验、人工确认"]
    M --> N["发布任务队列"]
    N --> O["状态、截图、日志、回滚记录"]
```

## 核心边界

- `models/` 定义统一内容 IR、平台草稿、校验问题和发布结果。
- `adapters/` 只负责平台规则、渲染、校验、模拟和发布动作。
- `agents/` 负责多 Agent 编排，不直接耦合平台实现。
- `services/` 负责业务用例编排，例如生成预览、创建发布任务、汇总校验报告。
- `tasks/` 负责异步执行和重试策略，正式发布不依赖 FastAPI `BackgroundTasks`。
- `automation/` 负责 Playwright 浏览器辅助发布和截图采集。

## 当前阶段范围

第一阶段（已交付）：形成模拟闭环：

1. 接收用户输入内容。
2. 标准化为内容 IR。
3. 生成四个平台的草稿预览。
4. 运行格式和合规校验。
5. 创建模拟发布任务。
6. 返回预览、校验报告、任务状态和截图占位记录。

第二阶段（核心已交付）：已接入真实发布：

- ✅ 账号凭据加密保存，公众号使用 AppID/AppSecret，B站使用 passport 登录后获取的 Cookie 凭据。
- ✅ 发布素材先上传到后端本地存储，再由平台 Adapter 上传到目标平台。
- ✅ 真实发布任务交给 Celery worker 执行，FastAPI 只负责创建任务和查询状态。
- ✅ `publication_records` 保存平台外部 ID、外部状态、响应快照和错误信息。
- 🔄 小红书 myaibot API Adapter 已就绪，前端账号登录入口和联调待补齐。

当前平台状态：

| 平台 | 预览 | 模拟发布 | 真实发布状态 |
|------|------|----------|--------------|
| 公众号 | 已支持 | 已支持 | 已接入素材上传、草稿创建、草稿发布和状态查询 |
| B站 | 已支持 | 已支持 | 已接入视频/封面上传、稿件提交、状态查询和测试稿件删除 |
| 小红书 | 已支持 | 已支持 | 已实现 myaibot API Adapter 和字段映射；账号入口与真实联调仍需补齐 |
| 知乎 | 已支持 | 已支持 | 暂不进入真实发布 API |

## 前端工作台架构

前端采用 **Vue 3 + TypeScript + Vite + Element Plus**，无 vue-router/Pinia，由 `App.vue` 通过 `activeTab` 内联管理四页签单页架构。

```
App.vue（状态枢纽）
├── 内容工作台（preview）
│   ├── EditorView           → 统一编辑 + 素材插入 + 文档导入 + Agent 触发
│   ├── PreviewView（弹窗）   → 多平台预览（公众号手机窗格 / B站播放器 / 知乎文章 / 小红书笔记）
│   │   └── WechatPreview    → 公众号手机模拟器样式
│   ├── AgentPreviewView     → Agent 优化结果展示（元数据 + 改写内容 + 平台草稿）
│   └── PublishConfirmView   → 发布确认（统一/独立配置切换）
│       └── PublishFormView  → 分平台表单（B站 / 公众号 / 小红书）
├── 任务看板（task）
│   └── TaskView             → 发布任务列表 + 状态刷新 + 草稿发布
├── 多媒体库（media）
│   └── MediaLibraryView     → 独立素材管理页
│       └── MediaLibraryPanel → 共享素材面板（图片/视频/音频/文件夹/IndexedDB）
└── 账号管理（account）
    └── AccountView          → 公众号连接 + B站验证码登录 + 密钥管理
```

主要数据流如下：

1. `EditorView` 维护标题、正文、标签、目标平台和 Agent 优化选项。
2. `MediaLibraryPanel` 维护共享素材库，素材数据通过 IndexedDB 和 localStorage 保存。
3. `buildContentPayload()` 汇总编辑区和素材引用，传给普通预览或 Agent 预览。
4. `PreviewView` 只读取 `preview.drafts.<platform>`，按平台分别渲染标题、摘要、章节标题、正文和素材。
5. `AgentPreviewView` 展示 `metadata`、`rewritten_content` 和各平台 draft，用户可选择应用 AI 建议。
6. `PublishConfirmView` 在统一配置和独立配置之间切换，生成用户确认后的发布字段。
7. `buildPublishTaskPayload()` 合并 `platform_options`、`asset_ids`、`content_blocks` 和 `inline_drafts`，提交给 `/api/v1/publish-tasks`。
8. `TaskView` 轮询任务状态，支持 `refresh`（刷新）和 `draft → publish`（草稿发布）操作。
9. `AccountView` 管理平台账号连接：公众号扫码、B站验证码登录、连接测试、密钥查看与删除。
10. `api/client.ts` 约 600 行 TypeScript，集中管理全部 17 个 API 调用函数和类型定义。

更细的字段来源见 [发布字段映射](./publish-field-mapping.md)。
