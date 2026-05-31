# Auto_Upt 鏈彁浜ゅ彉鏇存€荤粨

> 鏈€鍚庢洿鏂帮細2026-05-30锛堣凯浠?2锛?
> 鏈杩唬锛氬鍏ュ姛鑳芥帴鍏?ContentAnalystAgent 绔犺妭鍒嗘瀽 + 瀵煎叆鎸夐挳绉昏嚦缂栬緫鍖洪《閮?

---

## 馃攧 鏈€鏂拌凯浠ｏ細绔犺妭鍒嗘瀽 + 瀵煎叆鎸夐挳涓婄Щ锛?026-05-30 Iteration 2锛?

### 鍚庣锛歚ImportService` 鎺ュ叆 `ContentAnalystAgent`

| 鏂囦欢 | 鍙樻洿 |
|------|------|
| `backend/app/services/import_service.py` | `__init__` 鏂板 `self._analyst = ContentAnalystAgent()`锛沗import_document()` 杩斿洖鍓嶈皟鐢?`self._analyst.analyze()`锛岃緭鍑虹珷鑺?鍓爣棰?|
| `backend/app/schemas/content.py` | `ImportDocumentResponse` 鏂板 `subtitle` 鍜?`chapters` 瀛楁 |

**宸ヤ綔娴?*锛氭枃妗ｅ鍏?鈫?`DocumentExtractorAgent` 鎻愬彇鏍囬/鏍囩/姝ｆ枃 鈫?**`ContentAnalystAgent.analyze()`** 鈫?杩斿洖 chapters/subtitle 鈫?鍓嶇灞曠ず

### 鍓嶇锛氬鍏ユ寜閽Щ鑷抽《閮?+ 绔犺妭灞曠ず

| 鏂囦欢 | 鍙樻洿 |
|------|------|
| `frontend/src/views/EditorView.vue` | 妯℃澘锛氬鍏ユ寜閽?+ hidden input 浠庡簳閮?`.action-row` 绉昏嚦椤堕儴 `<el-form>` 涔嬪墠锛堣摑鑹茶櫄绾?`.import-bar`锛夛紱鑴氭湰锛歚handleImportFileChange` 鏂板绔犺妭缁撴瀯 console 鏃ュ織锛涙牱寮忥細鏂板 `.import-bar` / `.import-hint` 鏍峰紡 |
| `frontend/src/api/client.ts` | 鏂板 `ImportChapterPayload` 鎺ュ彛锛沗ImportDocumentResponse` 鏂板 `subtitle?`銆乣chapters?` 瀛楁 |

---

## 馃搵 绗竴杞彉鏇达紙2026-05-30 Iteration 1锛?

---

## 涓€銆佸悗绔彉鏇达紙Backend锛?

### 1. 鏂板鏂囦欢

| 鏂囦欢 | 鍔熻兘 |
|------|------|
| `backend/app/agents/llm_analyzer.py` | LLM 鍐呭鍒嗘瀽鍣紝瀹炵幇娣卞眰绔犺妭鍒嗘锛坄segment()`锛夛紝閫氳繃 DeepSeek V4 Pro 灏嗘鏂囧垏鍒嗕负 Chapter/MediaItem 缁撴瀯 |
| `backend/app/agents/document_extractor.py` | **鏂囨。鎻愬彇鏅鸿兘浣?* 鈥?浠庡鍏ョ殑 .md/.docx 鏂囨。閫氳繃 LLM + 瑙勫垯寮曟搸鎻愬彇鏍囬銆佹爣绛俱€佹鏂囥€佹憳瑕併€佸獟浣撲綅缃瓑缁撴瀯鍖栦俊鎭?|
| `backend/app/services/import_service.py` | **鏂囨。瀵煎叆鏈嶅姟** 鈥?瑙ｆ瀽 .md锛堟鍒欐彁鍙栧浘鐗囧紩鐢級銆?docx锛坧ython-docx 瑙ｆ瀽娈佃惤/鏍囬/琛ㄦ牸/宓屽叆鍥剧墖锛夊拰 .txt锛堢函鏂囨湰璇诲彇锛夛紝璋冪敤 `DocumentExtractorAgent` 杩斿洖 `ImportDocumentResponse` |

### 2. 骞冲彴閫傞厤鍣?鈥?澶氬钩鍙伴鏍兼覆鏌?

| 鏂囦欢 | 鍙樻洿姒傝 |
|------|----------|
| `backend/app/adapters/zhihu/renderer.py` | **閲嶅啓**锛氭柊澧?`_build_zhihu_blocks()` 杈撳嚭 7 绉嶇粨鏋勫寲鍧楋紙conclusion/heading-1/heading-2/text/separator/quote/image锛夛紝鏀寔绔犺妭鈫掑潡鏄犲皠 |
| `backend/app/adapters/xiaohongshu/renderer.py` | **閲嶅啓**锛氭柊澧?`_build_xhs_body()` + 灏忕孩涔﹂鏍?emoji 鍒楄〃 + 鐭彞鎷嗗垎锛岃緭鍑?`highlights` 瀛楁 |
| `backend/app/adapters/bilibili/renderer.py` | **閲嶅啓**锛氭柊澧?`_build_bilibili_body()` + 鏃堕棿鎴崇珷鑺傛槧灏?`_format_timestamp()`锛岃緭鍑?`content_points` |
| `backend/app/adapters/wechat/renderer.py` | 绉婚櫎 `clip_text` 鎴柇閫昏緫锛岀Щ闄ょ‖缂栫爜闀垮害闄愬埗锛屼繚鐣?Markdown 鍒板叕浼楀彿鏍煎紡杞崲 |
| `backend/app/adapters/*/profile.yaml` | 鍏ㄩ儴鏇存柊锛歚body_max_length: 0`锛堜笉闄愬埗姝ｆ枃闀垮害锛夛紝`title_max_length: 200`锛宍tags_max_count: 20` |
| `backend/app/adapters/wechat/adapter.py` | 寰皟閫傞厤鍣ㄦ帴鍙ｅ疄鐜?|
| `backend/app/adapters/bilibili/adapter.py` | 鍚屼笂 |

### 3. 鏅鸿兘浣撳眰

| 鏂囦欢 | 鍙樻洿姒傝 |
|------|----------|
| `backend/app/agents/content_analyst.py` | 闆嗘垚 `LLMContentAnalyzer`锛屾柊澧?`analyze()` 鏂规硶璋冪敤 LLM 鍒嗘锛岃繑鍥?`ContentAnalysis` |
| `backend/app/agents/orchestrator.py` | 缂栨帓閫昏緫鏇存柊锛氬洓骞冲彴鍏变韩涓€娆?LLM 璋冪敤鍚庡垎鍒€傞厤娓叉煋 |
| `backend/app/agents/platform_stylist.py` | 椋庢牸鎻愮ず璇嶅井璋?|

### 4. API 绔偣

| 鏂囦欢 | 鏂板/鍙樻洿 | 鍔熻兘 |
|------|-----------|------|
| `backend/app/api/v1/endpoints/content.py` | **鏂板** `POST /content/import` | 鏂囨。瀵煎叆绔偣锛氭帴鍙?.md/.docx 鏂囦欢涓婁紶锛岃皟鐢?`ImportService` 瑙ｆ瀽骞惰繑鍥?`ImportDocumentResponse` |
| `backend/app/api/v1/endpoints/previews.py` | **鏂板** `PUT /{preview_id}/drafts/{platform}` | 鍗曞钩鍙拌崏绋跨紪杈戠鐐癸細鎺ュ彈 `DraftUpdateRequest`锛坱itle/body/tags锛夛紝鐙珛鏇存柊鏌愬钩鍙拌崏绋?|

### 5. 鏈嶅姟灞?

| 鏂囦欢 | 鍙樻洿姒傝 |
|------|----------|
| `backend/app/services/preview_service.py` | 鏂板 `update_platform_draft()` 鏂规硶锛氭洿鏂板崟骞冲彴鑽夌鍚庨噸鏂版牎楠屽苟钀藉簱锛屾柊澧?`from adapters.registry import get_adapter` 瀵煎叆 |
| `backend/app/services/publish_service.py` | 鍙戝竷娴佺▼閫傞厤鏂扮殑澶氬钩鍙拌崏绋跨粨鏋?|

### 6. 鏁版嵁妯″瀷 & 閰嶇疆

| 鏂囦欢 | 鍙樻洿姒傝 |
|------|----------|
| `backend/app/schemas/content.py` | 鏂板 `DraftUpdateRequest`銆乣DraftUpdateResponse`銆乣ImportedMedia`銆乣ImportDocumentResponse` Pydantic 妯″瀷 |
| `backend/app/core/config.py` | 鏂板 OpenAI 閰嶇疆瀛楁鎵╁睍 |
| `requirements.txt` | 鏂板 `python-docx>=1.1,<2.0` 渚濊禆 |

---

## 浜屻€佸墠绔彉鏇达紙Frontend锛?

### 1. 瑙嗗浘缁勪欢

| 鏂囦欢 | 鍙樻洿姒傝 |
|------|----------|
| `frontend/src/views/PreviewView.vue` | **閲嶅ぇ閲嶅啓**锛氭柊澧?`localDrafts` 鐙珛鍝嶅簲寮忓壇鏈?+ 缂栬緫宸ュ叿鏍忥紙"鉁?缂栬緫XX鑽夌"鎸夐挳锛? 缂栬緫闈㈡澘锛坱itle/body/tags 杈撳叆妗嗭級+ `enterEdit()`/`cancelEdit()`/`saveDraft()` + `emit("update:drafts")`銆傜煡涔庢ā鏉挎柊澧?7 绉嶇粨鏋勫寲鍧楁覆鏌擄紙`.zh-conclusion`/`.zh-h1`/`.zh-h2`/`.zh-text`/`.zh-sep`/`.zh-quote`/`.zh-image`锛夊強瀹屾暣 CSS |
| `frontend/src/views/EditorView.vue` | **鏂板鏂囨。瀵煎叆鍔熻兘**锛氭柊澧?瀵煎叆鏂囨。"鎸夐挳 + 闅愯棌 `<input type="file">` + `importLoading` 鐘舵€?+ `handleImportClick()`/`handleImportFileChange()` 鑷姩濉厖 title/tags/content |
| `frontend/src/App.vue` | **寮圭獥 UI 閲嶅啓**锛歚.el-dialog` CSS `!important` 瑕嗙洊 + flex 甯冨眬 + sticky header/footer + `overflow-y: auto` body銆傛柊澧?`handleDraftUpdate()` 鑽夋鏇存柊澶勭悊 + `@update:drafts` 浜嬩欢缁戝畾銆傛槧灏?`zhihu_blocks` 鍒?PreviewProps |
| `frontend/src/views/WechatPreview.vue` | 鍏紬鍙烽瑙堟牱寮忛€傞厤 |
| `frontend/src/views/PublishFormView.vue` | 鍙戝竷琛ㄥ崟閫傞厤鏂扮殑澶氬钩鍙拌崏绋跨粨鏋?|
| `frontend/src/views/PublishConfirmView.vue` | 鍙戝竷纭椤靛井璋?|

### 2. API 瀹㈡埛绔?

| 鏂囦欢 | 鍙樻洿姒傝 |
|------|----------|
| `frontend/src/api/client.ts` | 鏂板绫诲瀷锛歚ZhihuBlockPayload`锛? 绉嶅潡绫诲瀷锛夈€乣DraftUpdatePayload`銆乣DraftUpdateResponse`銆乣ImportedMediaPayload`銆乣ImportDocumentResponse`銆傛柊澧炲嚱鏁帮細`updatePlatformDraft()`銆乣importDocument()`銆備慨澶?`PublishTaskCreatePayload` 鎺ュ彛 |

### 3. 鍏朵粬

| 鏂囦欢 | 鍙樻洿姒傝 |
|------|----------|
| `.env.example` | 鏂板/鏇存柊鐜鍙橀噺绀轰緥 |

---

## 涓夈€佹柊澧炲伐浣滃尯鏂囦欢

| 鏂囦欢 | 璇存槑 |
|------|------|
| `agent_res1.md` | AI Agent 鍝嶅簲鍙傝€冩枃妗?|
| `agent_res1.pdf` | AI Agent 鍝嶅簲鍙傝€?PDF |

---

## 鍥涖€佸姛鑳藉垎绫绘€荤粨

### 澶氬钩鍙伴鏍兼覆鏌擄紙鍘婚檺鍒?+ 椋庢牸鍖栵級
- 鍥涘钩鍙?renderer 閲嶅啓锛岀Щ闄ゆ墍鏈夐暱搴︽埅鏂?
- profile.yaml 缁熶竴鎻愬崌闄愬埗涓婇檺
- 鐭ヤ箮 7 绉嶇粨鏋勫寲鍧椼€佸皬绾功 emoji + 鐭彞銆丅绔欐椂闂存埑绔犺妭

### 寮圭獥 UI 鍥哄畾锛坔eader/footer 涓嶉殢婊氬姩婧㈠嚭锛?
- `App.vue` 寮圭獥 CSS 瀹屽叏閲嶅啓
- sticky header锛堟爣棰?+ 鍏抽棴鎸夐挳锛? sticky footer锛堟搷浣滄寜閽級

### 鐭ヤ箮缁撴瀯鍖栨覆鏌?
- 鍚庣 `zhihu/renderer.py` 杈撳嚭 `zhihu_blocks`
- 鍓嶇 `PreviewView.vue` 娓叉煋 7 绉嶅潡绫诲瀷骞?CSS 缇庡寲
- `client.ts` 鏂板 `ZhihuBlockPayload` 绫诲瀷

### 澶氬钩鍙扮嫭绔嬬紪杈?
- 鍚庣 PUT 绔偣 + `update_platform_draft()` 鏈嶅姟鏂规硶
- 鍓嶇 `PreviewView.vue` 缂栬緫闈㈡澘 + `localDrafts` 鐙珛鍓湰
- 缂栬緫鏁版嵁娴佸洖 preview.drafts 渚涘悗缁彂甯冧娇鐢?

### 鏂囨。瀵煎叆 + LLM 鎻愬彇
- 鍚庣 `POST /content/import` 绔偣
- `import_service.py` 瑙ｆ瀽 .md/.docx
- `document_extractor.py` LLM + 瑙勫垯寮曟搸鎻愬彇缁撴瀯鍖栦俊鎭?
- 鍓嶇 `EditorView.vue` 瀵煎叆鎸夐挳 + 鑷姩濉厖

---

## 浜斻€佸緟瀹屾垚浜嬮」

- [ ] 閫氳繃 `.venv` 瀹夎 `python-docx`锛歚.venv\Scripts\python.exe -m ensurepip && .venv\Scripts\python.exe -m pip install python-docx`
- [ ] 杩愯 `docker compose up -d postgres redis` 鍚姩渚濊禆鏈嶅姟
- [ ] 杩愯 `uvicorn backend.app.main:app --reload` 鍚姩鍚庣
- [ ] 杩愯 `cd frontend && npm run dev` 鍚姩鍓嶇
- [ ] 鎻愪氦鎵€鏈夊彉鏇村埌 Git
