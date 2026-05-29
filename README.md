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

当前只建立第一阶段框架和接口说明，主要文件都保留了待实现方法、类职责、输入输出约定和 TODO。
