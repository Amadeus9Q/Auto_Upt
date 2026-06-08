# Auto_Upt

多平台创作内容自动发布工具。

本项目采用“内容中台 + 平台适配器 + AI Agent 发布助理”的架构：

- 内容中台负责把用户输入的 Markdown、富文本、视频信息统一转换为内容 IR。
- 平台适配器负责把内容 IR 渲染成公众号、B站、知乎、小红书等平台的草稿。
- AI Agent 编排层负责内容分析、平台风格改写、格式校验、合规检查、发布执行和失败恢复建议。
- 第一阶段只做内容编辑、AI 适配、格式校验和模拟发布，不接入真实发布。

## 第一阶段目标

输入一篇文章后，生成四类平台预览：

- 公众号长文版
- 知乎回答/专栏版
- 小红书图文笔记版
- B站视频简介/动态版

模拟发布会生成预览、校验报告、任务状态和截图占位记录。真实发布能力在后续阶段接入。

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

当前已实现第一阶段 MVP：内容输入、多平台预览、预览落库、模拟发布任务和模拟 Agent 编排。

第二阶段后端已开始接入公众号和 B站真实发布能力：账号凭据加密保存、本地素材上传、真实发布任务、Celery worker、发布记录和 Alembic 迁移。真实平台联调需要配置对应平台账号和开放平台参数。

## 本地环境变量

项目根目录的 `.env.example` 是环境变量模板。首次本地运行前，建议复制一份为 `.env`：

```powershell
Copy-Item .env.example .env
```

然后按本地环境修改 `.env` 中的数据库、Redis、模型服务、平台接口或密钥配置。后端通过 `backend/app/core/config.py` 自动读取 `.env`；如果 `.env` 不存在，会使用代码中的默认值，但数据库、Redis 或外部平台服务不符合默认配置时仍可能在运行时连接失败。

注意：`.env.example` 可以提交到仓库，`.env` 通常不要提交，因为里面可能包含 API Key、平台密钥或账号凭据。
