# MVP 范围说明（给后续开发者）

本文档说明当前「商品知识库 RAG + 直播复盘 + 轻量运营看板」MVP 的实现范围，
方便后续交付、复查和继续开发。封版提交：`8f919a1`。

---

## 一、当前已实现

### 1. 商品管理
- 商品 CRUD、搜索、直播状态筛选、分页、CSV 导入导出（`/products*`）。
- 字段：名称、价格、核心卖点、适用人群、用户痛点、优惠信息、库存、直播状态、备注。

### 2. 商品知识库（RAG）
- 按商品上传 PDF / TXT / MD / CSV（`POST /products/{id}/knowledge/upload`），文本按 800 字符分块、120 字符重叠。
- 文档列表（`GET /products/{id}/knowledge/documents`）、查看片段（`GET .../documents/{filename}/chunks`）、
  删除（`DELETE .../documents/{filename}`）、重建该文件索引（`POST .../documents/{filename}/reindex`）。
- 问答（`POST /products/{id}/knowledge/ask`）：商品维度过滤 + 字符级 n-gram TF-IDF 检索（`app/rag.py`），
  取 Top-K 片段构造 prompt 调用大模型；回答附带 `sources`（文件名、片段序号、内容前 200 字）。
- prompt 包含商品基础资料、检索到的知识片段与用户问题；要求不脱离资料编造、不使用绝对化表述。
- 同名文件重传会先删除旧片段（幂等覆盖）。

### 3. 直播话术
- `POST /products/{id}/live-scripts`：基于商品资料生成七模块话术（开场引入 / 卖点讲解 / 痛点刺激 /
  互动提问 / 优惠逼单 / 异议回应 / 结尾转化）。
- LLM 不可用时降级为本地兜底话术（`build_live_script_fallback`），资料缺失处使用诚实占位文案；
  状态字段记录 `success / fallback / failed`，前端可区分展示。

### 4. 评论回复
- `POST /products/{id}/comment-replies`：基于商品信息 + 观众评论生成主播口吻回复。
- prompt 约束：只使用资料已有信息、不编造功效/库存/售后、不绝对化表述；本地兜底按评论关键词分流
  （价格类 / 适用人群类 / 质量类 / 通用），资料缺失时不编造。

### 5. 直播复盘
- `POST /products/{id}/live-reviews`：复盘数据源 = 商品资料 + 已记录运营数据（话术数、评论回复数、
  知识库文档数、最近 10 条「评论 + AI 回复」）。
- 输出固定四模块标题：**用户关注点 / 常见异议 / 高频问题 / 下场直播优化建议**。
- prompt 明确禁止编造直播场次、销量、GMV、转化率、观看人数等未统计指标；评论样本不足时会声明
  "当前评论样本较少"。
- 本地兜底（`build_live_review_fallback`）的缺失字段判断基于原始字段值，不会被默认占位文案误判。

### 6. 轻量运营看板
- `GET /live-ops/dashboard`：`product_count`、`live_product_count`、`live_script_count`、
  `comment_reply_count`、`live_review_count`、`knowledge_document_count`、
  `hot_questions`（按评论文本简单计数 Top5）、`recent_comment_replies`、`recent_live_reviews`。
- 旧接口 `GET /dashboard/stats` 保留，前端 `loadOpsStats` 先调新接口、失败回退旧接口。

### 7. LLM 调用与降级
- OpenAI-compatible 接口（默认 DeepSeek），`LLM_PROVIDER=openai_compatible`；
  `mock` 模式返回本地固定文案（不调用外部 API）。
- 超时、重试（429/5xx）、`FALLBACK_MESSAGE` 识别，所有 AI 功能都有本地兜底，演示不中断。

### 8. 测试
- pytest + FastAPI TestClient，临时 SQLite + mock LLM，全量 346 个用例通过。
- 覆盖：知识库上传/列表/片段/重建/删除、问答 prompt 结构、话术与回复、复盘四标题与兜底缺失判断、
  看板字段与用户隔离、鉴权、上传大小限制等。

---

## 二、当前刻意未实现（保持 MVP 轻量）

| 未实现项 | 原因 / 说明 |
|---|---|
| 真实直播平台接入 | 评论来自界面模拟输入，不接抖音/快手/淘宝等平台 API 或 Webhook |
| WebSocket / 实时评论流 | 无实时推送，评论回复为手动触发 |
| 直播场次管理 | 没有场次模型；复盘基于商品维度全部已记录数据，不按场次聚合 |
| Agent 扩展 | 已随旧 CRM 功能移除（`chore: remove legacy CRM` 系列提交），不再保留 `/agent/analyze` |
| 向量检索改造 | 商品知识库固定使用 TF-IDF；通用 RAG 页支持向量检索但默认关闭（`VECTOR_SEARCH_ENABLED=false`） |
| 多租户 / 复杂权限 | 仅管理员 + 普通用户两级，数据按 `user_id` 隔离；公开注册默认关闭 |
| Redis / Celery / 消息队列 | 无异步任务，AI 调用同步执行 |
| 前端框架 | 单文件 `static/index.html` 原生 JS，未引入构建工具 |

---

## 三、已知限制

1. **商品知识库「重建该文件索引」为诚实 no-op**：TF-IDF 每次即时计算、无索引可重建，
   接口固定返回 `{"reindexed": false, "message": "商品知识库使用本地关键词检索，无需重建索引"}`。
   通用 RAG 页的同名按钮在向量未启用时同样返回"向量搜索未启用"。
2. **mock 模式问答不体现资料内容**：`LLM_PROVIDER=mock` 时问答返回固定提示文案；
   要展示"回答来自资料"，必须配置真实 LLM。
3. **复盘不统计真实直播指标**：观看人数、销量、GMV 等未记录即不展示、不编造；复盘质量依赖评论样本量。
4. **TF-IDF 检索效果**：字符 n-gram 对中文可用，但无语义理解；同义词、口语化问法召回率有限。
5. **数据库**：默认 SQLite（`customer_assistant.db`），适合单机演示；生产可用 PostgreSQL（已支持连接串）。
6. **真实 LLM 依赖外网**：断网时各功能走本地兜底，status 为 `fallback`。
7. **真实 LLM 输出不可完全预测**：prompt 已约束不编造，但回复措辞会随模型变化（例如会引用资料中的库存数字）。

---

## 四、下一阶段建议（按优先级）

1. **向量检索升级**：接入 Embedding API + ChromaDB 替换/混合 TF-IDF，提升语义召回；
   同时让商品知识库的上传/重建索引接入向量写入，使「重建该文件索引」具备真实语义。
2. **直播场次模型**：增加场次表，评论回复、复盘、看板按场次聚合，支撑"下场直播优化建议"更精准。
3. **真实平台接入**：通过平台 Webhook 接收真实评论、自动触发回复（需运营审核），逐步替换模拟输入。
4. **看板可视化**：统计卡片之外增加趋势图（话术/回复/复盘随时间变化）、高频问题词云。
5. **数据迁移**：引入 Alembic 管理正式数据库 schema 变更。
6. **CI / 质量门禁**：GitHub Actions 跑 pytest；提交前自动跑全量测试。
7. **回复质量评测**：对评论回复/问答构建小样本评测集（人工标注），持续调优 prompt。

---

## 五、相关文件索引

- 启动与配置：`README.md`、`.env.example`
- 演示步骤：`docs/demo-guide.md`
- 接口实现：`app/main.py`（路由）、`app/llm.py`（prompt 与兜底）、`app/rag.py`（解析/分块/TF-IDF）
- 数据模型：`app/models.py`（`Product`、`ProductKnowledgeChunk`、`LiveScript`、`LiveCommentReply`、`LiveReview`）
- 测试：`tests/test_product_knowledge.py`、`tests/test_live_reviews.py`、`tests/test_comment_replies.py`、`tests/test_live_scripts.py`
