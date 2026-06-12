# Auto_Upt 贡献指南

感谢参与 Auto_Upt 开发。项目当前处于多平台内容工作台和真实发布链路持续完善阶段，修改时应优先保证现有业务边界、平台安全和文档一致性。

## 1. 开始之前

建议先阅读：

1. [项目 README](./README.md)：了解能力范围、启动方式和当前平台支持状态。
2. [文档总览](./docs/README.md)：按修改类型找到对应设计和流程文档。
3. [系统架构](./docs/architecture.md)：了解前后端、Agent、Adapter 和发布服务边界。
4. [MVP 路线](./docs/mvp-roadmap.md)：确认功能是否属于当前阶段。

当前阶段不要默认实现真实账号授权、浏览器自动发布或生产自动化。涉及这些能力时，应先明确需求和安全边界。

## 2. 环境准备

安装后端和前端依赖：

```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

复制 `.env.example` 为 `.env`，至少配置数据库连接。需要保存平台账号时，必须配置并妥善保管 `CREDENTIAL_ENCRYPTION_KEY`。

本地开发推荐分别启动依赖、后端、异步发布任务执行器和前端：

```powershell
.\scripts\start-containers.ps1
.\scripts\start-backend.ps1
.\scripts\start-worker.ps1
cd frontend
npm run dev
```

也可以使用 Docker Compose：

```powershell
docker compose up -d --build
```

更多命令见 [scripts/README.md](./scripts/README.md)。

## 3. 修改边界

### 后端

- API 路由只负责请求解析、依赖注入和响应，不直接放置业务逻辑。
- 业务用例放在 `backend/app/services/`。
- 平台渲染、规则、校验和发布行为放在 `backend/app/adapters/<platform>/`。
- Agent 不直接依赖具体平台实现，应通过工具或 Adapter 能力协作。
- 数据结构变更需要同步修改 SQLAlchemy 模型、Alembic migration 和数据库文档。

### 前端

- 当前 `App.vue` 是全局状态枢纽；跨工作区状态由其持有，局部 UI 状态留在对应 View。
- 子组件通过 `defineModel` 或事件与父组件交互，不要创建重复且无法同步的状态副本。
- 平台名称、能力和公共错误处理优先复用 `frontend/src/utils/` 中已有工具。
- 修改流程节点、平台草稿或发布确认状态前，先阅读 [前端状态流](./docs/frontend-state-flow.md)。

### 平台 Adapter

新增平台应创建：

```text
backend/app/adapters/<platform>/
  adapter.py
  renderer.py
  profile.yaml
```

平台规则必须优先进入 profile 或 Adapter，不要硬编码到核心发布服务。详细约定见 [平台扩展设计](./docs/adapter-extension.md)。

## 4. 安全边界

- 不要提交 `.env`、API Key、AppSecret、账号密码、Cookie 或真实平台响应中的敏感字段。
- 不要在日志、测试输出、截图或 PR 描述中暴露凭据。
- `CREDENTIAL_ENCRYPTION_KEY` 一旦用于保存账号后不得随意更换。
- 自动化测试默认不得调用真实平台发布接口。
- `external_publish` 测试必须使用专用测试账号、隔离环境并由人工明确启用。
- 删除素材、账号、任务或数据库卷前，确认逻辑引用和恢复方案。

## 5. 开发流程

1. 从目标分支创建功能或修复分支。
2. 阅读相关模块和对应文档，确认当前实现边界。
3. 保持修改范围聚焦，避免同时进行无关重构。
4. 为行为变更补充相应测试。
5. 更新受影响的 API、流程、字段映射或架构文档。
6. 执行适合本次修改范围的验证。
7. 检查差异，确认没有临时文件、生成文件或敏感配置。
8. 按功能组织提交并创建 PR。

## 6. 验证要求

### 基础检查

```powershell
cd frontend
npm run build
cd ..
python -m pytest -m "not live and not external_publish"
python -m compileall backend
git diff --check
```

根据修改范围选择验证：

| 修改范围 | 至少执行 |
|---|---|
| 仅文档 | `git diff --check`，检查相对链接和 Mermaid 图 |
| 前端状态或交互 | `npm run build`，并手动验证相关完整流程 |
| 后端服务或 API | 对应 pytest，用 FastAPI 文档或客户端验证接口 |
| 数据库模型 | 新增 migration，执行 `alembic upgrade head` 并验证已有数据升级 |
| Agent | Agent 单元/集成测试，验证无密钥、超时和连接错误路径 |
| 平台 Adapter | 渲染与校验测试；真实调用必须人工明确授权 |
| Docker | `docker compose config`、构建、启动和健康检查 |

自动化测试分层和部署环境测试命令见 [自动化测试说明](./docs/automated-testing.md)。

## 7. 测试约定

- 新增后端测试放在 `tests/`，文件名使用 `test_*.py`。
- 默认测试不能依赖外网、真实账号或真实平台发布。
- 需要运行中部署环境的测试使用 `live` marker。
- 可能调用真实发布接口的测试使用 `external_publish` marker，并默认跳过。
- 测试应覆盖成功路径、前置条件缺失和可恢复失败。
- 修改测试用例范围时，同步更新 `docs/test-cases-full-lifecycle.csv` 和 `docs/automated-testing.md`。

## 8. 文档联动

功能变更不能只修改代码。至少检查：

| 变更 | 相关文档 |
|---|---|
| API 请求或响应 | `docs/api-contract.md` |
| 前端流程、状态或回退规则 | `docs/frontend-state-flow.md`、对应流程文档 |
| Agent 工具、超时或降级 | `docs/agent-workflow.md` |
| 发布表单、字段或素材要求 | `docs/publish-field-mapping.md`、`docs/publish-flow.md` |
| 账号配置和状态 | `docs/account-flow.md` |
| 素材和持久化 | `docs/storage-and-data.md` |
| 数据库模型或迁移 | `docs/database-schema.md` |
| 新增平台 | `docs/adapter-extension.md`、`docs/architecture.md`、`docs/mvp-roadmap.md` |

完整联动规则见 [文档总览](./docs/README.md)。

## 9. 提交规范

建议使用 Conventional Commits 风格：

```text
feat(frontend): add platform selection feedback
fix(backend): preserve publication status refresh
docs: document storage lifecycle
test: cover simulated publish lifecycle
refactor(adapter): simplify profile loading
```

常用类型：

| 类型 | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `docs` | 文档修改 |
| `test` | 测试新增或调整 |
| `refactor` | 不改变外部行为的重构 |
| `chore` | 工具、依赖和维护任务 |

提交应按功能组织。不要把无关前端、后端、文档或格式化改动混入同一提交。

## 10. PR 检查清单

创建 PR 前确认：

- [ ] PR 描述说明问题、解决方案和影响范围。
- [ ] 已列出实际执行的验证命令和结果。
- [ ] 未包含密钥、账号凭据或真实用户数据。
- [ ] 没有意外修改无关文件。
- [ ] API、流程、字段和架构文档已按需更新。
- [ ] 新行为已有对应测试或说明未测试原因。
- [ ] 真实发布行为已明确标注，并经过人工确认。
- [ ] 已知限制和后续工作已记录。

## 11. Issue 与设计讨论

提交较大功能前，建议先明确：

- 用户问题和验收标准；
- 当前阶段是否允许；
- 涉及的平台和真实发布风险；
- 前后端、Agent、Adapter 和数据库边界；
- 数据迁移、兼容和回滚方式；
- 测试与文档计划。

避免在实现过程中隐式扩大功能范围。对于尚未支持的平台能力，应明确标注为待补齐或暂不支持。

