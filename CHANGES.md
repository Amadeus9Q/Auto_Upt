# Auto_Upt 未提交变更总结

> 生成时间：2026-05-30  
> 变更范围：28 个已修改文件 + 5 个新增文件，共 1836 行新增 / 377 行删除

---

## 一、后端变更（Backend）

### 1. 新增文件

| 文件 | 功能 |
|------|------|
| `backend/app/agents/llm_analyzer.py` | LLM 内容分析器，实现深层章节分段（`segment()`），通过 DeepSeek V4 Pro 将正文切分为 Chapter/MediaItem 结构 |
| `backend/app/agents/document_extractor.py` | **文档提取智能体** — 从导入的 .md/.docx 文档通过 LLM + 规则引擎提取标题、标签、正文、摘要、媒体位置等结构化信息 |
| `backend/app/services/import_service.py` | **文档导入服务** — 解析 .md（正则提取图片引用）、.docx（python-docx 解析段落/标题/表格/嵌入图片）和 .txt（纯文本读取），调用 `DocumentExtractorAgent` 返回 `ImportDocumentResponse` |

### 2. 平台适配器 — 多平台风格渲染

| 文件 | 变更概要 |
|------|----------|
| `backend/app/adapters/zhihu/renderer.py` | **重写**：新增 `_build_zhihu_blocks()` 输出 7 种结构化块（conclusion/heading-1/heading-2/text/separator/quote/image），支持章节→块映射 |
| `backend/app/adapters/xiaohongshu/renderer.py` | **重写**：新增 `_build_xhs_body()` + 小红书风格 emoji 列表 + 短句拆分，输出 `highlights` 字段 |
| `backend/app/adapters/bilibili/renderer.py` | **重写**：新增 `_build_bilibili_body()` + 时间戳章节映射 `_format_timestamp()`，输出 `content_points` |
| `backend/app/adapters/wechat/renderer.py` | 移除 `clip_text` 截断逻辑，移除硬编码长度限制，保留 Markdown 到公众号格式转换 |
| `backend/app/adapters/*/profile.yaml` | 全部更新：`body_max_length: 0`（不限制正文长度），`title_max_length: 200`，`tags_max_count: 20` |
| `backend/app/adapters/wechat/adapter.py` | 微调适配器接口实现 |
| `backend/app/adapters/bilibili/adapter.py` | 同上 |

### 3. 智能体层

| 文件 | 变更概要 |
|------|----------|
| `backend/app/agents/content_analyst.py` | 集成 `LLMContentAnalyzer`，新增 `analyze()` 方法调用 LLM 分段，返回 `ContentAnalysis` |
| `backend/app/agents/orchestrator.py` | 编排逻辑更新：四平台共享一次 LLM 调用后分别适配渲染 |
| `backend/app/agents/platform_stylist.py` | 风格提示词微调 |

### 4. API 端点

| 文件 | 新增/变更 | 功能 |
|------|-----------|------|
| `backend/app/api/v1/endpoints/content.py` | **新增** `POST /content/import` | 文档导入端点：接受 .md/.docx 文件上传，调用 `ImportService` 解析并返回 `ImportDocumentResponse` |
| `backend/app/api/v1/endpoints/previews.py` | **新增** `PUT /{preview_id}/drafts/{platform}` | 单平台草稿编辑端点：接受 `DraftUpdateRequest`（title/body/tags），独立更新某平台草稿 |

### 5. 服务层

| 文件 | 变更概要 |
|------|----------|
| `backend/app/services/preview_service.py` | 新增 `update_platform_draft()` 方法：更新单平台草稿后重新校验并落库，新增 `from adapters.registry import get_adapter` 导入 |
| `backend/app/services/publish_service.py` | 发布流程适配新的多平台草稿结构 |

### 6. 数据模型 & 配置

| 文件 | 变更概要 |
|------|----------|
| `backend/app/schemas/content.py` | 新增 `DraftUpdateRequest`、`DraftUpdateResponse`、`ImportedMedia`、`ImportDocumentResponse` Pydantic 模型 |
| `backend/app/core/config.py` | 新增 OpenAI 配置字段扩展 |
| `requirements.txt` | 新增 `python-docx>=1.1,<2.0` 依赖 |

---

## 二、前端变更（Frontend）

### 1. 视图组件

| 文件 | 变更概要 |
|------|----------|
| `frontend/src/views/PreviewView.vue` | **重大重写**：新增 `localDrafts` 独立响应式副本 + 编辑工具栏（"✎ 编辑XX草稿"按钮）+ 编辑面板（title/body/tags 输入框）+ `enterEdit()`/`cancelEdit()`/`saveDraft()` + `emit("update:drafts")`。知乎模板新增 7 种结构化块渲染（`.zh-conclusion`/`.zh-h1`/`.zh-h2`/`.zh-text`/`.zh-sep`/`.zh-quote`/`.zh-image`）及完整 CSS |
| `frontend/src/views/EditorView.vue` | **新增文档导入功能**：新增"导入文档"按钮 + 隐藏 `<input type="file">` + `importLoading` 状态 + `handleImportClick()`/`handleImportFileChange()` 自动填充 title/tags/content |
| `frontend/src/App.vue` | **弹窗 UI 重写**：`.el-dialog` CSS `!important` 覆盖 + flex 布局 + sticky header/footer + `overflow-y: auto` body。新增 `handleDraftUpdate()` 草案更新处理 + `@update:drafts` 事件绑定。映射 `zhihu_blocks` 到 PreviewProps |
| `frontend/src/views/WechatPreview.vue` | 公众号预览样式适配 |
| `frontend/src/views/PublishFormView.vue` | 发布表单适配新的多平台草稿结构 |
| `frontend/src/views/PublishConfirmView.vue` | 发布确认页微调 |

### 2. API 客户端

| 文件 | 变更概要 |
|------|----------|
| `frontend/src/api/client.ts` | 新增类型：`ZhihuBlockPayload`（7 种块类型）、`DraftUpdatePayload`、`DraftUpdateResponse`、`ImportedMediaPayload`、`ImportDocumentResponse`。新增函数：`updatePlatformDraft()`、`importDocument()`。修复 `PublishTaskCreatePayload` 接口 |

### 3. 其他

| 文件 | 变更概要 |
|------|----------|
| `.env.example` | 新增/更新环境变量示例 |

---

## 三、新增工作区文件

| 文件 | 说明 |
|------|------|
| `agent_res1.md` | AI Agent 响应参考文档 |
| `agent_res1.pdf` | AI Agent 响应参考 PDF |

---

## 四、功能分类总结

### 多平台风格渲染（去限制 + 风格化）
- 四平台 renderer 重写，移除所有长度截断
- profile.yaml 统一提升限制上限
- 知乎 7 种结构化块、小红书 emoji + 短句、B站时间戳章节

### 弹窗 UI 固定（header/footer 不随滚动溢出）
- `App.vue` 弹窗 CSS 完全重写
- sticky header（标题 + 关闭按钮）+ sticky footer（操作按钮）

### 知乎结构化渲染
- 后端 `zhihu/renderer.py` 输出 `zhihu_blocks`
- 前端 `PreviewView.vue` 渲染 7 种块类型并 CSS 美化
- `client.ts` 新增 `ZhihuBlockPayload` 类型

### 多平台独立编辑
- 后端 PUT 端点 + `update_platform_draft()` 服务方法
- 前端 `PreviewView.vue` 编辑面板 + `localDrafts` 独立副本
- 编辑数据流回 preview.drafts 供后续发布使用

### 文档导入 + LLM 提取
- 后端 `POST /content/import` 端点
- `import_service.py` 解析 .md/.docx
- `document_extractor.py` LLM + 规则引擎提取结构化信息
- 前端 `EditorView.vue` 导入按钮 + 自动填充

---

## 五、待完成事项

- [ ] 通过 `.venv` 安装 `python-docx`：`.venv\Scripts\python.exe -m ensurepip && .venv\Scripts\python.exe -m pip install python-docx`
- [ ] 运行 `docker compose up -d postgres redis` 启动依赖服务
- [ ] 运行 `uvicorn backend.app.main:app --reload` 启动后端
- [ ] 运行 `cd frontend && npm run dev` 启动前端
- [ ] 提交所有变更到 Git
