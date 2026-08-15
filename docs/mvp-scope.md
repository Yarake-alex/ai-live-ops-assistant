# MVP 范围说明（给后续开发者）

本文档说明当前「商品资料文档 + 开播话术 + 评论助手 + 直播复盘 + 运营工作台」MVP 的实现范围
（含 V2「资料检索增强 + 开播准备工作流」轻量版），方便后续交付、复查和继续开发。

---

## 一、当前已实现

### 1. 商品资料
- 商品 CRUD、搜索、直播状态筛选、分页、CSV 导入导出（`/products*`）。
- 字段：名称、价格、核心卖点、适用人群、用户痛点、优惠信息、库存、直播状态、备注。

### 2. 商品资料文档（RAG，V2 已增强检索）
- 按商品上传 PDF / TXT / MD / CSV（`POST /products/{id}/knowledge/upload`），文本按 800 字符分块、120 字符重叠。
- 文档列表（`GET /products/{id}/knowledge/documents`）、查看片段（`GET .../documents/{filename}/chunks`）、
  删除（`DELETE .../documents/{filename}`）、重建资料索引（`POST .../documents/{filename}/reindex`）。
- 问答（`POST /products/{id}/knowledge/ask`）：**优先商品资料向量检索**（真实 Embedding + 本地 Chroma，
  独立 collection `product_knowledge_chunks`，按 `user_id + product_id + source_type=product_knowledge` 过滤），
  Embedding / 索引不可用、索引不完整或检索异常时**自动降级**商品维度 TF-IDF（`app/rag.py::retrieve_product_chunks_vector`）；
  取 Top-K 片段构造 prompt 调用大模型；回答附带 `sources`（文件名、片段序号、内容前 200 字）。
- **上传即索引**：上传成功后尝试生成 Embedding 写入本地 Chroma，失败仅记录日志、不影响上传成功。
- **索引生命周期**：同名重传先清旧向量再重写；删除文档同步清理向量（清理失败返回 `vector_warning` 提示）；
  重建资料索引真实生效（清理旧索引 → 重新 Embedding → 写入）；向量未启用时返回 `reindexed: false` 与运营语言提示。
- prompt 包含商品基础资料、检索到的知识片段与用户问题；要求不脱离资料编造、不使用绝对化表述。

### 3. 商品资料完整度与开播准备（V2）
- `GET /products/{id}/readiness`：**实时计算，不落库、不调用 LLM**，返回 `completeness`（`score` / `missing_items` / `suggestions`）与 `prep_checklist`（当前为空数组占位）。
- 12 项确定性规则：名称非空、`price > 0`、`stock > 0`、直播状态、核心卖点、适用人群、用户痛点、优惠信息、商品资料文档存在、FAQ 类文件名（`faq` / `问答` / `Q&A`）、售后类文件名（`售后` / `退换` / `after`）、风险边界（`notes` 非空或文件名含 `风险` / `边界` / `禁用` / `不可承诺` / `合规`）。
- `score = 命中数 / 12 × 100` 取整；`missing_items` 与 `suggestions` 均为确定性映射的运营语言文案。
- 前端：商品资料页展示完整度百分比、缺失项、下一步建议（选中商品 / 上传 / 删除 / 重建 / 编辑后自动刷新）；
  运营工作台提供轻量「开播准备」入口。**不做任务系统**（无负责人、截止时间、提醒、已读状态）。

### 4. 直播话术
- `POST /products/{id}/live-scripts`：基于商品资料生成七模块话术（开场引入 / 卖点讲解 / 痛点刺激 /
  互动提问 / 优惠逼单 / 异议回应 / 结尾转化）。
- LLM 不可用时降级为本地兜底话术（`build_live_script_fallback`），资料缺失处使用诚实占位文案；
  状态字段记录 `success / fallback / failed`，前端可区分展示。

### 5. 评论助手
- `POST /products/{id}/comment-replies`：基于商品信息 + 观众评论生成主播口吻回复。
- prompt 约束：只使用资料已有信息、不编造功效/库存/售后、不绝对化表述；本地兜底按评论关键词分流
  （价格类 / 适用人群类 / 质量类 / 通用），资料缺失时不编造。

### 6. 直播复盘
- `POST /products/{id}/live-reviews`：复盘数据源 = 商品资料 + 已记录运营数据（话术数、评论回复数、
  知识库文档数、最近 10 条「评论 + AI 回复」）。
- 输出固定四模块标题：**用户关注点 / 常见异议 / 高频问题 / 下场直播优化建议**。
- prompt 明确禁止编造直播场次、销量、GMV、转化率、观看人数等未统计指标；评论样本不足时会声明
  "当前评论样本较少"。
- 本地兜底（`build_live_review_fallback`）的缺失字段判断基于原始字段值，不会被默认占位文案误判。

### 7. 运营工作台
- `GET /live-ops/dashboard`：`product_count`、`live_product_count`、`live_script_count`、
  `comment_reply_count`、`live_review_count`、`knowledge_document_count`、
  `hot_questions`（按评论文本简单计数 Top5）、`recent_comment_replies`、`recent_live_reviews`。
- 旧接口 `GET /dashboard/stats` 保留，前端 `loadOpsStats` 先调新接口、失败回退旧接口。
- 首页提供轻量「开播准备」横幅入口，引导到商品资料页查看资料完整度（无后端聚合接口、无任务列表）。

### 8. LLM 调用与降级
- OpenAI-compatible 接口（默认 DeepSeek），`LLM_PROVIDER=openai_compatible`；
  `mock` 模式返回本地固定文案（不调用外部 API）。
- 超时、重试（429/5xx）、`FALLBACK_MESSAGE` 识别，所有 AI 功能都有本地兜底，演示不中断。

### 9. 测试
- pytest + FastAPI TestClient，临时 SQLite + mock LLM + 内置 `test` embedding provider（不依赖真实外部 API）。
- 当前验证结果：`tests/test_product_knowledge.py` 38 个用例通过；全量 325 个用例通过、1 个既有 fixture 弃用 warning。
- 覆盖：知识库上传/列表/片段/重建/删除、问答 prompt 结构、商品资料向量检索与 TF-IDF 降级（配置关闭 /
  存储不可用 / 不支持 / embedding 异常 / 失效 id）、重建资料索引、删除/重传索引清理、用户/商品隔离、
  完整度评分（低分/满分/文件名规则/隔离/鉴权）、话术与回复、复盘四标题与兜底缺失判断、看板字段与用户隔离、
  鉴权、上传大小限制等。
- 真实 Embedding + Chroma 已手工验证通过：直播素材库 `vector_indexed == chunks`；商品资料
  `product_knowledge_chunks` 向量数与 SQL 片段对齐；同义问题可召回目标片段（资料写「换季脆弱肌适用」，
  提问「敏感肌能不能用？」命中该片段）。

---

## 二、当前刻意未实现（保持 MVP 轻量）

| 未实现项 | 原因 / 说明 |
|---|---|
| 真实直播平台接入 | 评论来自界面模拟输入，不接抖音/快手/淘宝等平台 API 或 Webhook |
| WebSocket / 实时评论流 | 无实时推送，评论回复为手动触发 |
| 直播场次管理 | 没有场次模型；复盘基于商品维度全部已记录数据，不按场次聚合 |
| Agent 扩展 / 旧 CRM | 已随旧 CRM 功能移除（`chore: remove legacy CRM` 系列提交），不再保留 `/agent/analyze` |
| pgvector / PostgreSQL 向量列 | 商品资料文档与直播素材库均使用本地 Chroma/SQLite；pgvector 场景自动降级基础检索，未做 PostgreSQL schema 扩展 |
| 开播准备任务系统 | 仅资料完整度评分 + 轻量入口；无负责人、截止时间、提醒、已读状态 |
| 部门 / 主管 / 人事权限、复杂 RBAC | 仅管理员 + 普通用户两级，数据按 `user_id` 隔离；公开注册默认关闭 |
| 多租户 SaaS | 单部署单组织，不做租户隔离 |
| 手机 App / 小程序 | 仅 Web 页面（桌面/移动浏览器自适应） |
| Redis / Celery / Kubernetes / 消息队列 | 无异步任务，AI 调用同步执行；无编排依赖 |
| 前端框架 | 单文件 `static/index.html` 原生 JS，未引入构建工具 |

---

## 三、已知限制

1. **未配置向量检索时「重建该文件索引」返回诚实提示**：接口返回
   `{"reindexed": false, "message": "资料索引功能未启用"}`，商品问答自动使用基础资料检索，不影响功能；
   配置后重建真实生效。
2. **mock 模式问答不体现资料内容**：`LLM_PROVIDER=mock` 时问答返回固定提示文案；
   要展示"回答来自资料"，必须配置真实 LLM。
3. **复盘不统计真实直播指标**：观看人数、销量、GMV 等未记录即不展示、不编造；复盘质量依赖评论样本量。
4. **基础检索（TF-IDF）效果**：字符 n-gram 对中文可用，但无语义理解；同义词、口语化问法召回率有限——
   该路径仅作为 Embedding 未配置/不可用时的降级；配置后商品资料问答与直播素材库均走语义检索。
5. **数据库**：默认 SQLite（`customer_assistant.db`），适合单机演示；生产可用 PostgreSQL（已支持连接串）。
6. **真实 LLM 依赖外网**：断网时各功能走本地兜底，status 为 `fallback`。
7. **真实 LLM 输出不可完全预测**：prompt 已约束不编造，但回复措辞会随模型变化（例如会引用资料中的库存数字）。

---

## 四、下一阶段建议（按优先级）

1. **向量检索生产扩展（可选）**：商品资料文档与直播素材库已完成真实 Embedding + 本地 Chroma 语义检索；
   如需 PostgreSQL 生产部署，可评估 pgvector 方案（当前 pgvector 场景自动降级基础检索）。
2. **直播场次模型**：增加场次表，评论助手、复盘、看板按场次聚合，支撑"下场直播优化建议"更精准。
3. **真实平台接入**：通过平台 Webhook 接收真实评论、自动触发回复（需运营审核），逐步替换模拟输入。
4. **看板可视化**：统计卡片之外增加趋势图（话术/回复/复盘随时间变化）、高频问题词云。
5. **数据迁移**：引入 Alembic 管理正式数据库 schema 变更。
6. **CI / 质量门禁**：GitHub Actions 跑 pytest；提交前自动跑全量测试。
7. **回复质量评测**：对评论助手/问答构建小样本评测集（人工标注），持续调优 prompt。

---

## 五、相关文件索引

- 启动与配置：`README.md`、`.env.example`
- 演示步骤：`docs/demo-guide.md`
- V2 设计说明：`docs/v2-design.md`
- 接口实现：`app/main.py`（路由、完整度评分）、`app/llm.py`（prompt 与兜底）、
  `app/rag.py`（解析/分块/检索与降级）、`app/vector_store.py`（本地 Chroma 商品资料与通用素材双 collection）、
  `app/embeddings.py`（OpenAI-compatible Embedding）
- 数据模型：`app/models.py`（`Product`、`ProductKnowledgeChunk`、`LiveScript`、`LiveCommentReply`、`LiveReview`）
- 测试：`tests/test_product_knowledge.py`、`tests/test_live_reviews.py`、`tests/test_comment_replies.py`、`tests/test_live_scripts.py`
