# 发布确认 —— 业务流程图

> 描述从用户确认发布到平台真实发布完成的前后端通讯过程。

---

## 泳道图

```mermaid
sequenceDiagram
    autonumber
    actor User as 创作者
    participant Confirm as 前端 PublishConfirmView
    participant API as 后端 PublishService
    participant Worker as Celery Worker / Adapter
    participant Platform as 外部平台
    participant Board as 前端任务看板

    rect rgb(234, 242, 255)
        Note over User,Confirm: 流程节点 3：发布确认
        Confirm->>API: GET /api/v1/accounts
        API-->>Confirm: 账号状态、账号名称与平台 ID
        Confirm-->>User: 展示可选平台和连接状态
        User->>Confirm: 选择账号、发布模式并确认字段
        User->>Confirm: 点击确认发布
        Confirm->>Confirm: 准备封面与正文引用素材
        Confirm->>API: POST /api/v1/publish-tasks
    end

    activate API
    API->>API: 校验模式、平台、账号与素材
    alt 模拟发布
        API->>API: 同步生成模拟结果
        API-->>Board: 返回模拟任务结果
    else 保存草稿或真实发布
        API->>API: 保存任务快照
        API->>Worker: 推送异步发布任务
        API-->>Board: 返回 pending 任务

        loop 每个目标平台
            Worker->>Platform: 上传素材并提交草稿 / 发布
            alt 平台处理成功
                Platform-->>Worker: external_id / external_status
                Worker->>API: 保存 PublicationRecord 与成功结果
            else 平台处理失败
                Platform-->>Worker: 错误码与失败原因
                Worker->>API: 保存失败结果与处理建议
            end
        end
        API-->>Board: 返回最新任务状态
    end
    deactivate API

    rect rgb(237, 248, 241)
        Board-->>User: 展示平台步骤、状态和失败原因
    end
```

---

## 步骤详解

### Step 1：进入发布确认页

用户完成预览后进入「发布确认」页。页面加载时请求 `GET /api/v1/accounts` 获取各平台账号状态，据此过滤可选平台：模拟模式全平台可选，真实发布仅已连接账号的平台可选。

### Step 2：配置发布字段

两种配置方式：

| 方式 | 说明 |
|------|------|
| **统一配置** | 全局标题/摘要同步到所有平台，各平台只填专属字段（如 B站分区、公众号作者） |
| **独立配置** | 各平台独立编辑标题/正文/摘要/标签，默认值由 Agent 生成的 draft 填充 |

### Step 3：提交发布任务

前端将草稿快照、平台配置、账号ID、素材ID 合并为 Payload，发送 `POST /api/v1/publish-tasks`。草稿快照不依赖 `previews` 表外键，用户关闭页面后任务仍可执行。

### Step 4：后端处理

- **模拟模式**：直接同步返回各平台假结果，不入队列。
- **真实发布**：创建 `PublishTask` 记录 → 校验账号凭据 → 推送 Celery 队列。

### Step 5：异步发布到平台

Celery Worker 拉取任务，逐平台调用 Adapter 执行真实发布：

| 平台 | 核心流程 |
|------|---------|
| 公众号 | 获取 access_token → 上传素材 → 创建草稿（draft）/ 提交发布（publish） |
| B站 | Cookie 鉴权 → 上传视频分片 → 上传封面 → 提交稿件 |
| 小红书 | 签名认证 → 上传图片/视频 → 创建笔记 |

每平台发布完成后保存 `PublicationRecord`（external_id、external_url、响应结果）。全平台成功 → 任务状态 `succeeded`，任一失败 → `failed`。

### Step 6：前端任务看板

`TaskView` 展示任务列表，每条任务显示各平台步骤时间线（上传→创建→发布），支持刷新状态、草稿转发布等操作。

---

## 三种发布模式

| 模式 | 调用平台API | 异步执行 | 用途 |
|------|:---:|:---:|------|
| `simulate` | ❌ | ❌ | 演示/测试工作流 |
| `draft` | ✅ 创建草稿 | ✅ Celery | 公众号预览后人工确认再发布 |
| `publish` | ✅ 直接发布 | ✅ Celery | 正式发布 |

---

## 关键设计决策

| 决策 | 原因 |
|------|------|
| 草稿快照保存在任务中 | 不依赖 previews 外键，离线可靠执行 |
| 用户确认优先 | 发布前可覆盖 Agent 生成字段 |
| Celery 异步 | 视频上传耗时长，不阻塞 API 响应 |
| 凭据加密存储 | AppSecret/Cookie 加密入库，仅发布时解密 |

---

> **相关文档**：[生成预览流程图](./preview-flow.md) · [账号登录流程图](./account-flow.md) · [API 契约](./api-contract.md) · [发布字段映射](./publish-field-mapping.md)
