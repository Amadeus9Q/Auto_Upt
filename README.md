# Auto_Upt

多平台创作内容自动发布工具。

本项目采用“内容中台 + 平台适配器 + AI Agent 发布助理”的架构：

- 内容中台负责把用户输入的 Markdown、富文本、视频信息统一转换为内容 IR。
- 平台适配器负责把内容 IR 渲染成公众号、B站、知乎、小红书等平台的草稿。
- AI Agent 编排层负责内容分析、平台风格改写、格式校验、合规检查和失败恢复建议。
- 发布链路采用“预览 → 人工确认 → 创建发布任务”的方式，真实发布能力按平台逐步接入。

## 演示视频链接

- 百度网盘链接: https://pan.baidu.com/s/1oQ5dcYsLzLt2VmYnB0rnCw?pwd=fst3 提取码: fst3
- bilibili: https://www.bilibili.com/video/BV1rbVQ6HEo5/

## 当前能力

输入一篇文章后，可以生成四类平台预览：

- 公众号长文版
- 知乎回答/专栏版
- 小红书图文笔记版
- B站视频简介/动态版

当前前端工作台包含：

- 统一内容编辑区：标题、正文、标签、目标平台、Agent 优化选项。
- 共享素材库：图片、视频、音频、封面、多级文件夹和正文素材引用。
- 平台预览窗口：按公众号、B站、知乎、小红书分别渲染标题、摘要、正文、章节标题、标签和素材。
- 发布确认页：统一配置或分平台配置发布字段，再创建模拟、草稿或发布任务。
- 账号管理页：公众号和 B站连接入口已接入；知乎和小红书仍是占位。
- 任务看板：展示发布任务、平台结果、真实发布记录和可继续操作的草稿。

当前后端能力：

- 内容标准化、平台草稿生成、校验报告和预览快照。
- Agent 预览编排：规则引擎默认可用，配置 `OPENAI_API_KEY` 后可尝试 LLM 增强并失败回退。
- 公众号：素材上传、草稿创建、草稿提交发布、状态查询。
- B站：登录凭据保存、视频/封面上传、稿件提交、状态查询、测试稿件删除。
- 小红书：已实现 myaibot API Adapter 和字段映射；账号管理连接入口与真实联调仍需补齐。
- 知乎：当前仅支持预览和模拟，不进入真实发布 API。

## 技术栈规划

- 后端：Python + FastAPI
- 任务队列：Celery + Redis
- 数据库：PostgreSQL
- 浏览器自动化：Playwright
- 前端：Vue 3 + Element Plus
- AI Agent：OpenAI Responses API / Agents SDK 或兼容 Agent 框架

## 目录

```text
backend/   FastAPI、Celery、平台 Adapter、AI Agent、服务层骨架
frontend/  Vue3 + Element Plus 前端工作台骨架
docs/      架构、接口、平台扩展和阶段路线说明
tests/     后续测试用例目录
```

## 当前状态

当前已实现第一阶段 MVP，并扩展了部分第二阶段发布能力：

- 第一阶段：内容输入、多平台预览、校验报告、模拟发布任务和 Agent 预览编排。
- 第二阶段：公众号、B站真实发布链路已接入；小红书 API Adapter 已加入但仍需账号入口和联调；知乎暂不接入真实发布。

真实平台联调需要配置数据库、Redis、Celery worker、平台账号凭据和对应开放平台参数。

## 部署注意事项

### 环境变量

Docker Compose 部署前，请在项目根目录创建 `.env` 文件（可参考 `.env.example`）：

```ini
# 必须配置
CREDENTIAL_ENCRYPTION_KEY=<用 fernet 生成的密钥>
OPENAI_API_KEY=<你的 API Key>

# 可选
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
PUBLIC_BASE_URL=http://你的服务器IP或域名
```

> ⚠️ **`CREDENTIAL_ENCRYPTION_KEY` 一旦设定不可更改**，否则所有已保存的平台账号凭据将永久无法解密。
>
> 生成方式：`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### 数据卷保护

```bash
# ✅ 正常停止（保留所有数据）
docker compose down

# ❌ 危险操作：会删除 PostgreSQL 数据卷，所有账号设置、发布记录等将永久丢失
docker compose down -v
```

生产环境请定期备份 PostgreSQL 数据卷，或使用外部管理的数据库服务。

