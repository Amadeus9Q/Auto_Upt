# 账号登录 —— 业务流程图

> 描述用户在各平台配置账号、验证凭据、管理连接状态的前后端通讯过程。
> 当前公众号（AppID/AppSecret）和 B站（用户名+极验）已实现；知乎、小红书待第三阶段。

---

## 泳道图

```mermaid
flowchart TB
    subgraph USER["👤 创作者（AccountView）"]
        U1["进入账号配置页"]
        U2["公众号：填写 AppID / AppSecret"]
        U3["B站：填写用户名密码<br/>完成极验验证码"]
        U4["测试连接<br/>验证凭据是否有效"]
        U5["断开连接 / 清除历史凭据"]
    end

    subgraph FE["🖥️ 前端"]
        F1["GET /api/v1/accounts<br/>加载各平台账号状态"]
        F2["公众号：匹配历史 AppID<br/>POST /reveal-secret 自动填充"]
        F3["POST /wechat/connect"]
        F4["GET /bilibili/captcha<br/>加载极验 SDK 渲染滑块"]
        F5["POST /bilibili/login"]
        F6["POST /{platform}/test"]
        F7["DELETE /{account_id}"]
    end

    subgraph BE["⚙️ 后端（FastAPI + AccountService）"]
        B1["查询各平台最新账号记录"]
        B2["公众号连接<br/>解密历史凭据 / 获取 access_token<br/>AES-256-GCM 加密保存"]
        B3["B站获取验证码参数<br/>{gt, challenge, token}"]
        B4["B站登录<br/>获取 RSA 公钥 → 加密密码<br/>提交登录 → 获取 Cookie<br/>加密保存 Cookie"]
        B5["测试连接<br/>解密凭据 → 调用平台 API 验证"]
        B6["删除账号记录"]
    end

    subgraph PLATFORM["🌐 外部平台"]
        P1["微信公众平台<br/>/cgi-bin/token"]
        P2["B站登录 API<br/>captcha → RSA key → login"]
    end

    %% 初始化
    U1 --> F1
    F1 -->|"HTTP GET"| B1
    B1 -->|"AccountListResponse"| F1
    F1 -->|"展示状态卡片"| U1

    %% 公众号连接
    U2 -->|"输入/选择 AppID"| F2
    F2 -->|"自动填充 AppSecret"| U2
    U2 --> F3
    F3 -->|"HTTP POST"| B2
    B2 --> P1
    P1 -->|"access_token"| B2
    B2 -->|"AccountPlatformResponse"| F3
    F3 -->|"连接成功"| U1

    %% B站连接
    U3 -->|"获取验证码"| F4
    F4 -->|"HTTP GET"| B3
    B3 --> P2
    P2 -->|"gt/challenge/token"| B3
    B3 -->|"CaptchaResponse"| F4
    F4 -->|"渲染滑块"| U3
    U3 -->|"滑块通过 + 密码"| F5
    F5 -->|"HTTP POST"| B4
    B4 --> P2
    P2 -->|"Cookie"| B4
    B4 -->|"BilibiliLoginResponse"| F5
    F5 -->|"登录成功"| U1

    %% 测试 / 断开
    U4 --> F6
    F6 -->|"HTTP POST"| B5
    B5 --> P1 & P2
    P1 & P2 -->|"验证结果"| B5
    B5 -->|"AccountTestResponse"| F6
    F6 -->|"ok / fail"| U1

    U5 --> F7
    F7 -->|"HTTP DELETE"| B6
    B6 -->|"deleted"| F7
    F7 -->|"已断开"| U1

    style USER fill:#e3f2fd,stroke:#1565c0
    style FE fill:#e8f5e9,stroke:#2e7d32
    style BE fill:#f3e5f5,stroke:#7b1fa2
    style PLATFORM fill:#e0e0e0,stroke:#424242
```

---

## 步骤详解

### Step 1：页面初始化

`AccountView` 挂载时请求 `GET /api/v1/accounts`，后端查询各平台最新账号记录并返回状态（connected / disconnected / placeholder）。公众号额外返回历史 AppID 列表供快速选择。

### Step 2：公众号连接

用户输入 AppID 时，前端自动匹配历史记录。若匹配到且未填 AppSecret，调用 `POST /reveal-secret` 从加密存储读取自动填充。

提交 `POST /wechat/connect` 后，后端：
1. 若复用历史凭据则解密读取 AppSecret。
2. 调用微信 `get_access_token` 验证凭据有效性。
3. 将 `{app_id, app_secret, access_token}` 以 AES-256-GCM 加密存入数据库。
4. 返回连接结果，前端更新卡片为「已连接」。

### Step 3：B站登录

B站登录需三步交互：

| 步骤 | 请求 | 说明 |
|------|------|------|
| ① 获取验证码 | `GET /bilibili/captcha` | 后端请求 B站获取 `{gt, challenge, token}` |
| ② 极验验证 | 前端 SDK | 加载极验滑块，用户完成验证，获得 `{challenge, validate, seccode}` |
| ③ 提交登录 | `POST /bilibili/login` | 后端获取 RSA 公钥 → 加密密码 → 提交 B站 → 返回 Cookie → 加密入库 |

登录成功后前端重置密码字段和验证码。

### Step 4：测试连接

已连接账号可随时验证凭据是否仍然有效：`POST /{platform}/test`。后端解密凭据后调用对应平台 API（公众号 `get_access_token` / B站 `nav_info`），返回验证结果并更新账号状态。

### Step 5：断开连接

`DELETE /api/v1/accounts/{id}` 删除账号记录，前端重置卡片为「未连接」。公众号还会清除已保存的历史凭据选项。

---

## 各平台账号支持情况

| 功能 | 公众号 | B站 | 知乎 | 小红书 |
|------|:---:|:---:|:---:|:---:|
| 连接方式 | AppID/AppSecret | 用户名+极验 | 第三阶段 | 第三阶段 |
| 凭据加密 | ✅ AES-256-GCM | ✅ AES-256-GCM | ❌ | ❌ |
| 历史凭据复用 | ✅ 自动填充 | — | — | — |
| 连接测试 | ✅ | ✅ | ❌ | ❌ |
| Token 过期管理 | ✅ 过期前刷新 | ❌ | — | — |
| 主动断开 | ✅ | ✅ | ❌ | ❌ |

---

## 关键设计决策

| 决策 | 原因 |
|------|------|
| AppSecret/Cookie 加密存储 | 凭据安全第一，不可明文入库 |
| 公众号历史凭据自动填充 | 降低重复输入 AppSecret 的摩擦 |
| 连接时默认验证 | 确保保存的凭据立即可用 |
| B站同平台仅保留最新记录 | Cookie 为唯一活跃凭据，避免多账号冲突 |
| 知乎/小红书待第三阶段 | 无官方发布 API，需浏览器自动化辅助 |

---

> **相关文档**：[生成预览流程图](./preview-flow.md) · [发布确认流程图](./publish-flow.md) · [API 契约](./api-contract.md) · [架构设计](./architecture.md)
