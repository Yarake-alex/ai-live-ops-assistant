# AI 直播运营助手 MVP

AI 直播运营助手 MVP 是一个面向直播电商运营场景的 AI 演示系统。

当前主线能力围绕直播运营人员的日常工作展开：商品资料维护、商品资料文档问答（语义检索 + 基础检索降级）、开播话术、评论助手、直播复盘、运营工作台、资料完整度评分、开播准备入口，以及问题记录、低风险本地快答与商品级问题洞察。系统把"开播前 → 直播中 → 下播后"的流程串成一条可演示的轻量工作流。

项目同时保留了通用「直播素材库」（独立于商品维度的资料问答）与安全加固、数据库工程化、pytest 自动化测试、Docker 部署等工程能力，适合作为 AI 应用工程师方向的综合展示项目。旧版 CRM（客户管理、跟进分析、待跟进、Agent 跟进助手）已在 `chore: remove legacy CRM features` 系列提交中下线，仅保留 Git 历史。

## 当前 MVP 功能（直播运营）

- **商品资料**：商品新增、列表、详情、修改、删除，覆盖价格、核心卖点、适用人群、用户痛点、优惠信息、库存、直播状态等字段，支持搜索、筛选、分页与 CSV 导入导出。
- **商品资料文档（RAG）**：按商品上传 PDF/TXT/MD/CSV 资料，支持文档列表、查看片段、重建资料索引、删除；问答优先语义检索（真实 Embedding + 本地 Chroma，独立 collection `product_knowledge_chunks`），Embedding 或索引不可用时自动降级商品维度 TF-IDF；上传、删除、重传、重建会同步维护本地索引；回答附带参考片段来源。
- **资料完整度评分**：`GET /products/{id}/readiness` 实时计算商品资料完整度（12 项确定性规则，不落库、不调用大模型），返回 `score`、`missing_items`、`suggestions`；商品资料页展示百分比、缺失项与下一步建议，运营工作台提供「开播准备」轻量入口。
- **问题记录与本地快答**：商品问答与评论助手输入沉淀 `product_question_logs`（只记问题不记回答内容，best-effort 写入不影响主流程）；价格/库存/优惠/适用人群/卖点等低风险问题按商品字段**本地规则直答**（不调 LLM、不走向量），字段为空不强答；售后/风险等问题一律走商品资料检索。
- **问题洞察**：`GET /products/{id}/question-insights` 返回高频问题 Top5、9 类分类统计、最近问题、未覆盖问题；前端商品资料页「问题洞察」卡片轻量展示，帮助运营发现重复问题与资料缺口。
- **直播话术**：基于商品资料生成七模块主播口播话术（开场引入 → 结尾转化）；AI 不可用时自动降级为本地兜底话术并诚实标注资料缺失项。
- **评论助手**：针对模拟观众评论，结合商品信息生成主播口吻回复；不做绝对化承诺，资料未覆盖的内容不编造。
- **直播复盘**：基于商品资料与已记录的评论/回复生成复盘，固定四个模块：用户关注点、常见异议、高频问题、下场直播优化建议；不编造直播场次、销量、GMV 等未统计指标。
- **运营工作台**：`GET /live-ops/dashboard` 返回商品数、话术数、评论回复数、复盘数、高频评论（hot_questions）与最近记录；保留旧接口 `/dashboard/stats` 兼容回退；首页提供轻量「开播准备」入口。

## 辅助能力与工程能力

- **直播素材库**（通用资料问答，辅助能力）：支持上传 PDF、TXT、MD、CSV 资料，基于资料检索生成回答（独立 collection `rag_chunks`）；与商品资料文档相互独立，商品问答只检索当前商品资料，不混检、不共用资料池。
- **安全加固**：支持 CORS 白名单、访问密码登录页 + HttpOnly Cookie 登录态、上传文件大小限制。
- **测试体系**：使用 pytest + FastAPI TestClient 覆盖核心接口、鉴权逻辑和上传限制。
- **Docker 部署**：支持通过 Dockerfile 和 docker-compose.yml 在云服务器上部署运行。

## 技术栈

- **后端框架**：FastAPI
- **ORM**：SQLAlchemy
- **数据库**：SQLite（本地开发）/ PostgreSQL（生产部署推荐）
- **配置管理**：pydantic-settings / `.env`
- **数据校验**：Pydantic
- **文档解析**：pypdf
- **文本检索**：scikit-learn TF-IDF（基础降级）+ Embedding + 本地 ChromaDB 语义索引
- **LLM 接口**：OpenAI-compatible API（支持 DeepSeek / 通义 / 智谱等兼容接口）
- **前端**：HTML、CSS、JavaScript
- **测试**：pytest、FastAPI TestClient
- **部署**：Docker、docker-compose

## 目录结构

```text
app/
├── main.py             # FastAPI 接口入口（含完整度评分、问题洞察）
├── config.py           # 环境变量配置
├── models.py           # SQLAlchemy 数据库模型
├── schemas.py          # Pydantic 请求/响应模型
├── database.py         # 数据库引擎与会话
├── db_init.py          # 数据库建表、字段升级、索引补建
├── llm.py              # LLM 调用封装
├── rag.py              # 文档解析、文本分块、检索与降级
├── embeddings.py       # Embedding 调用封装（OpenAI-compatible）
├── vector_store.py     # 本地 Chroma 向量索引（商品资料与通用素材双 collection）
└── question_insights.py # 问题分类、记录、本地快答、洞察统计

static/
└── index.html          # 前端单页应用

tests/
├── conftest.py         # pytest 测试配置与临时数据库
└── test_*.py           # 接口、检索、完整度、问题洞察等测试

docs/
├── demo-guide.md       # 演示操作指南
├── mvp-scope.md        # MVP 范围说明
├── v2-design.md        # V2 设计说明（资料检索增强 + 开播准备）
└── v3-design.md        # V3 设计说明（问题洞察 + 本地快答）

Dockerfile           # Docker 镜像构建文件
docker-compose.yml   # Docker Compose 启动配置
requirements.txt     # Python 依赖
.env.example         # 环境变量示例
.gitignore           # Git 忽略规则
README.md            # 项目说明
```

## 本地启动

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

Linux / macOS：

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

复制环境变量文件：

```bash
copy .env.example .env
```

Linux / macOS：

```bash
cp .env.example .env
```

启动项目：

```bash
python -m uvicorn app.main:app --reload
```

启动后访问：

```text
http://127.0.0.1:8000
```

API 文档地址：

```text
http://127.0.0.1:8000/docs
```

### 默认演示账号

| 账号 | 密码 |
|---|---|
| admin | 123456 |

- 使用 `.env.example` 默认配置时（`APP_ACCESS_PASSWORD=123456`），首次启动会自动创建该管理员账号，登录页输入 `admin / 123456` 即可。
- 若 `APP_ACCESS_PASSWORD` 留空（本地开发免登录模式），登录页输入任意密码即可进入，系统使用内置 admin 用户。

### 演示操作步骤

非技术演示人员的点击式操作步骤见 [docs/demo-guide.md](docs/demo-guide.md)；当前 MVP 的实现范围、刻意未实现项与后续建议见 [docs/mvp-scope.md](docs/mvp-scope.md)。

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DATABASE_URL` | 数据库连接地址，可用于本地、测试或部署环境，支持 SQLite / PostgreSQL | `sqlite:///./customer_assistant.db` |
| `MAX_UPLOAD_SIZE_MB` | 上传文件大小限制，单位 MB | `10` |
| `APP_ADMIN_USERNAME` | 首次启动自动创建的管理员用户名 | `admin` |
| `APP_ACCESS_PASSWORD` | 首次启动自动创建管理员账号时使用的登录密码，设置后所有业务接口需登录 | 空（本地开发免登录） |
| `ENABLE_PUBLIC_REGISTRATION` | 是否开放公开注册，生产环境建议保持 `false` | `false` |
| `SESSION_SECRET` | Cookie 签名密钥，`APP_ACCESS_PASSWORD` 设置时必填且 >= 32 字符 | 空 |
| `PUBLIC_SITE_URL` | 正式访问地址，建议填写 HTTPS 域名 | 空 |
| `APP_ENV` | 运行环境：`development` / `production` / `test` | `development` |
| `COOKIE_SECURE` | Cookie Secure 标志，HTTPS 部署设为 `true` | `false` |
| `LLM_PROVIDER` | `mock` 不调用真实模型；`openai_compatible` 使用真实 API | `mock` |
| `OPENAI_API_KEY` | LLM API Key | 空 |
| `OPENAI_BASE_URL` | LLM API 地址，例如 `https://api.deepseek.com` | 空 |
| `OPENAI_MODEL` | 模型名称，例如 `deepseek-chat` | `deepseek-chat` |
| `CORS_ORIGINS` | 允许跨域访问的前端地址，多个地址用英文逗号分隔 | 本地开发地址 |

本地开发推荐：

```env
LLM_PROVIDER=mock
APP_ACCESS_PASSWORD=
APP_ADMIN_USERNAME=admin
ENABLE_PUBLIC_REGISTRATION=false
SESSION_SECRET=
APP_ENV=development
COOKIE_SECURE=false
MAX_UPLOAD_SIZE_MB=10
DATABASE_URL=sqlite:///./customer_assistant.db
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:8000
```

使用 DeepSeek 示例（与 `.env.example` 演示默认值一致）：

```env
LLM_PROVIDER=openai_compatible
OPENAI_API_KEY=your_deepseek_api_key_here
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

未配置真实 API Key 或网络不可用时，可临时设置 `LLM_PROVIDER=mock`：各 AI 功能返回本地 mock / 兜底内容，演示流程不会中断，但问答不会体现资料内容。

生产环境建议设置：

```env
APP_ADMIN_USERNAME=admin
APP_ACCESS_PASSWORD=your-admin-password
ENABLE_PUBLIC_REGISTRATION=false
SESSION_SECRET=<上一步生成的值>
APP_ENV=production
COOKIE_SECURE=true
MAX_UPLOAD_SIZE_MB=10
PUBLIC_SITE_URL=https://your-domain.com
DATABASE_URL=postgresql+psycopg://ai_customer:strong-password@postgres:5432/ai_customer
CORS_ORIGINS=https://your-domain.com
```

生成强随机 SESSION_SECRET：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

注意：
- HTTP IP 部署时 `COOKIE_SECURE=false`，HTTPS 域名部署时必须设为 `true`。
- `APP_ACCESS_PASSWORD` 设置后，系统首次启动会创建 `APP_ADMIN_USERNAME` 管理员账号。管理员可通过 `/auth/users` 创建普通用户。
- Cookie 使用 HMAC-SHA256 签名，HttpOnly 防 XSS 窃取。

## 数据库说明

- 默认使用 SQLite 数据库，适合本地开发和演示。
- 生产环境推荐使用 PostgreSQL，项目已支持 `postgresql+psycopg://...` 连接地址。
- 默认数据库文件为 `customer_assistant.db`。
- 支持通过 `DATABASE_URL` 修改数据库路径。
- Docker 单机演示可使用：`sqlite:///./data/customer_assistant.db`。
- Docker PostgreSQL 部署可使用 `docker-compose.postgres.yml`。
- 详细 PostgreSQL 生产部署指南请参阅 [POSTGRES_DEPLOYMENT.md](POSTGRES_DEPLOYMENT.md)。
- 启动时会自动建表、补字段、补索引。
- 数据库文件不应提交到 GitHub。

不应上传的数据库文件包括：

```text
*.db
*.db-wal
*.db-shm
*.sqlite
*.sqlite3
```

## Docker 部署

项目支持 Docker 部署，适合部署到云服务器。

### 1. 准备 `.env`

```bash
cp .env.example .env
```

编辑 `.env`：

```env
LLM_PROVIDER=openai_compatible
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

APP_ADMIN_USERNAME=admin
APP_ACCESS_PASSWORD=your-admin-password
ENABLE_PUBLIC_REGISTRATION=false
SESSION_SECRET=your-random-session-secret-at-least-32-chars
APP_ENV=production
COOKIE_SECURE=true
MAX_UPLOAD_SIZE_MB=10

PUBLIC_SITE_URL=https://your-domain.com
DATABASE_URL=postgresql+psycopg://ai_customer:strong-password@postgres:5432/ai_customer
CORS_ORIGINS=https://your-domain.com
```

### 2. 创建数据目录

```bash
mkdir -p data
```

### 3. 启动容器

```bash
docker compose up -d --build
```

如需使用 PostgreSQL 版本：

```bash
docker compose -f docker-compose.postgres.yml up -d --build
```

详细部署说明请参阅 [POSTGRES_DEPLOYMENT.md](POSTGRES_DEPLOYMENT.md)。

### 4. 查看运行状态

```bash
docker ps
```

查看日志：

```bash
docker logs -f ai-live-ops-assistant
```

访问项目：

```text
http://your-server-ip:8000
```

访问接口文档：

```text
http://your-server-ip:8000/docs
```

停止容器：

```bash
docker compose down
```

## 部署前检查 / 本地运行 / 服务器部署

### 本地启动命令

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

访问地址：`http://127.0.0.1:8000`，健康检查：`http://127.0.0.1:8000/health`

### 本地测试命令

```bash
# 全量测试
python -m pytest -q

# 直播运营核心模块测试（商品资料文档 / 直播复盘 / 评论助手 / 直播话术）
python -m pytest tests/test_product_knowledge.py tests/test_live_reviews.py tests/test_comment_replies.py tests/test_live_scripts.py -q
```

测试使用临时 SQLite 数据库，不污染正式数据。LLM 使用 mock 模式，避免调用外部 API。

### 服务器 .env 必填项

部署到服务器时，`.env` 至少需要配置以下变量：

```env
# ── 必填项 ──
APP_ACCESS_PASSWORD=your-strong-password
SESSION_SECRET=<python -c "import secrets; print(secrets.token_hex(32))" 生成的值>
APP_ENV=production
COOKIE_SECURE=false          # 如果暂时还是 HTTP；HTTPS 部署时必须设为 true
DATABASE_URL=sqlite:///./data/customer_assistant.db   # Docker 单机部署；生产推荐 PostgreSQL

# ── 安全相关 ──
APP_ADMIN_USERNAME=admin
ENABLE_PUBLIC_REGISTRATION=false
MAX_UPLOAD_SIZE_MB=10
```

注意：
- `APP_ACCESS_PASSWORD` 和 `SESSION_SECRET` 是必须设置的，否则系统无法启动。
- `SESSION_SECRET` 长度不少于 32 字符。
- HTTP IP 访问时 `COOKIE_SECURE=false`，HTTPS 域名部署后改为 `true`。

### Embedding / 向量检索配置

如果没有 Embedding API，生产环境先保持向量检索关闭：

```env
VECTOR_SEARCH_ENABLED=false
```

等拿到 Embedding API 后再开启：

```env
VECTOR_SEARCH_ENABLED=true
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_API_KEY=your-embedding-api-key
EMBEDDING_BASE_URL=https://your-embedding-api-endpoint
EMBEDDING_MODEL_NAME=text-embedding-v4
EMBEDDING_DIMENSION=0          # 0 = 自动检测模型输出维度，或根据模型填写具体值
```

常见 Embedding API 兼容示例：
- **阿里云百炼 (Qwen)**：`EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`，`EMBEDDING_MODEL_NAME=text-embedding-v4`
- **智谱 (Zhipu)**：`EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4`，`EMBEDDING_MODEL_NAME=embedding-3`
- **与 LLM 同源**：如果 Embedding 和 LLM 使用同一个 API 地址和 Key，可以留空 `EMBEDDING_API_KEY` 和 `EMBEDDING_BASE_URL`，系统会自动沿用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。

向量存储说明（V2）：

- 向量存储为**本地 Chroma/SQLite**，无需额外服务。
- 直播素材库使用 collection `rag_chunks`；商品资料文档使用独立 collection `product_knowledge_chunks`——两者不混检、不共用资料池。
- 商品资料问答按 `user_id + product_id` 隔离检索，不跨用户、不跨商品召回。
- 自动化测试使用内置 `test` embedding provider，不依赖真实外部 API；未配置 Embedding 时各问答功能自动降级基础资料检索。

Docker 部署时，向量检索同样需要在 `.env` 中配置上述变量，`docker-compose.yml` 会自动加载。

### Docker 部署步骤

```bash
# 1. 准备环境变量
cp .env.example .env
# 编辑 .env，填写必填项（见上方"服务器 .env 必填项"）

# 2. 创建数据目录
mkdir -p data

# 3. 构建并启动
docker compose up -d --build

# 4. 检查健康状态
curl http://127.0.0.1:8000/health
# 或浏览器访问 http://your-server-ip:8000

# 5. 查看日志
docker logs -f ai-live-ops-assistant

# 6. 停止
docker compose down
```

## 接口说明

| 端点 | 方法 | 说明 | 需登录 |
|---|---|---|---|
| `/` | GET | 前端页面 | 否 |
| `/health` | GET | 健康检查 | 否 |
| `/auth/login` | POST | 登录（获取 Cookie） | 否 |
| `/auth/users` | POST | 管理员创建普通用户 | 是 |
| `/auth/register` | POST | 公开注册（默认关闭） | 否 |
| `/auth/logout` | POST | 退出登录 | 否 |
| `/auth/me` | GET | 当前登录状态 | 否 |
| `/products` | GET / POST | 商品列表 / 新增商品 | 是 |
| `/products/search` | GET | 商品搜索、筛选、分页 | 是 |
| `/products/import` | POST | 商品 CSV 导入（支持中英文表头） | 是 |
| `/products/export` | GET | 商品 CSV 导出（仅当前用户） | 是 |
| `/products/{id}` | GET / PUT / DELETE | 商品详情 / 修改 / 删除 | 是 |
| `/products/{id}/knowledge/upload` | POST | 上传商品资料文档（PDF/TXT/MD/CSV） | 是 |
| `/products/{id}/knowledge/documents` | GET | 商品资料文档列表 | 是 |
| `/products/{id}/knowledge/documents/{filename}/chunks` | GET | 查看文档片段 | 是 |
| `/products/{id}/knowledge/documents/{filename}/reindex` | POST | 重建该文件索引 | 是 |
| `/products/{id}/knowledge/documents/{filename}` | DELETE | 删除商品资料文档 | 是 |
| `/products/{id}/knowledge/ask` | POST | 基于商品资料问答（RAG） | 是 |
| `/products/{id}/readiness` | GET | 商品资料完整度与开播准备（实时计算） | 是 |
| `/products/{id}/question-insights` | GET | 商品级问题洞察（高频/分类/最近/未覆盖） | 是 |
| `/products/{id}/live-scripts` | GET / POST | 直播话术列表 / 生成直播话术 | 是 |
| `/products/{id}/comment-replies` | GET / POST | 评论回复历史 / 生成评论回复 | 是 |
| `/products/{id}/live-reviews` | GET / POST | 复盘历史 / 生成直播复盘 | 是 |
| `/live-ops/dashboard` | GET | 运营工作台 | 是 |
| `/dashboard/stats` | GET | 旧版统计（前端回退兼容） | 是 |
| `/rag/upload` | POST | 上传通用素材文档 | 是 |
| `/rag/documents` | GET | 通用素材文档列表 | 是 |
| `/rag/documents/{filename}` | DELETE | 删除指定文档 | 是 |
| `/rag/documents` | DELETE | 清空直播素材库 | 是 |
| `/rag/ask` | POST | 基于直播素材库问答 | 是 |

登录方式：打开页面后输入访问密码，登录成功后通过 HttpOnly Cookie 自动携带登录态。

## 商品 CSV 导入导出格式

导入（`POST /products/import`）支持两种表头：

| 英文表头 | 中文表头 | 说明 |
|---|---|---|
| `name` | 商品名称 | 必填；同一用户名下重复会跳过 |
| `price` | 价格 | 数字，可为小数；空值按 0 处理 |
| `selling_points` | 核心卖点 | 可选 |
| `target_audience` | 适用人群 | 可选 |
| `pain_points` | 用户痛点 | 可选 |
| `promotion` | 优惠信息 | 可选 |
| `stock` | 库存 | 非负整数；空值按 0 处理 |
| `live_status` | 直播状态 | 可选，空值默认「未上播」 |
| `notes` | 备注 | 可选 |

导出（`GET /products/export`）使用英文表头（含 `created_at`），文件为 UTF-8-SIG 编码（带 BOM，Excel 可直接打开）。导入导出均只作用于当前登录用户的数据。

## 安全加固

项目加入了基础安全加固能力：

- 生产环境建议设置 `APP_ADMIN_USERNAME`、`APP_ACCESS_PASSWORD` 和 `SESSION_SECRET`；
- 首次启动自动创建管理员账号，管理员可创建普通用户；
- 商品、直播运营数据与知识库资料按用户隔离；
- 所有业务接口需要先通过登录页认证，基于 HMAC-SHA256 签名 Cookie；
- Cookie 使用 HttpOnly 标志，防止 XSS 窃取；
- Cookie Secure 标志可通过 `COOKIE_SECURE` 配置；
- CORS 通过 `CORS_ORIGINS` 配置白名单；
- 上传文件通过 `MAX_UPLOAD_SIZE_MB` 限制大小；
- `.env` 和数据库文件禁止提交到 GitHub；
- 生产环境不建议使用 `--reload` 启动。

示例：

```env
APP_ADMIN_USERNAME=admin
APP_ACCESS_PASSWORD=your-admin-password
ENABLE_PUBLIC_REGISTRATION=false
SESSION_SECRET=<随机 32 字符以上密钥>
COOKIE_SECURE=true
PUBLIC_SITE_URL=https://your-domain.com
CORS_ORIGINS=https://your-domain.com
MAX_UPLOAD_SIZE_MB=10
```

## 测试说明

运行测试：

```bash
python -m pytest
```

测试覆盖内容：

- 商品新增、列表查询、搜索、CSV 导入导出；
- 商品资料文档上传、片段查看、重建索引、删除与 RAG 问答；
- 商品资料向量检索、TF-IDF 降级、删除/重传索引清理、用户/商品隔离；
- 商品资料完整度评分（12 项规则、缺失项与建议）；
- 问题分类规则（9 类关键词、risk 优先）与问题日志写入（best-effort）；
- 本地快答（价格/库存/优惠/人群/卖点，零 LLM/向量调用证明）与高风险不快答；
- 问题洞察接口（高频/分类/最近/未覆盖统计、用户与商品隔离）；
- 直播话术、评论助手、直播复盘与本地兜底；
- 运营工作台字段、计数与用户隔离；
- 未登录请求业务接口返回 401；
- 错误密码登录返回 401；
- 正确密码登录成功并返回 HttpOnly Cookie；
- Cookie 不包含明文密码；
- GET /auth/me 返回登录状态；
- 退出登录后再次请求返回 401；
- 首页 / 和静态资源不需要登录；
- 上传超大文件返回 413；
- 上传小 TXT 文件成功；
- RAG 问答、直播运营接口等受登录保护。

测试说明：

- 测试使用临时 SQLite 数据库；
- 不污染正式 `customer_assistant.db`；
- LLM 使用 mock 模式，避免真实调用外部 API。

## 直播运营版本演进

| 版本 | 能力 | 说明 |
|---|---|---|
| V1 | 直播运营 MVP | 商品资料、商品资料文档问答、开播话术、评论助手、直播复盘、运营工作台 |
| V2 | 资料检索增强 + 开播准备 | 商品资料语义检索、资料完整度评分、开播准备入口 |
| V3 | 问题洞察 + 本地快答（当前） | 商品问题记录与分类、低风险本地规则快答、商品级问题洞察接口与前端面板 |

## 后续规划

- **V4 建议方向：问题驱动的资料补齐与话术优化**：把问题洞察中的高频问题、未覆盖问题反哺到资料完整度建议、开播话术与直播复盘的输入，让系统从"记录问题"走向"用问题改进内容"。

## 项目说明

本项目为 AI 直播运营助手 MVP，当前版本为 **直播运营 V3（问题洞察 + 本地快答）**，演示链路覆盖「商品资料 → 资料文档问答 → 开播话术 → 评论助手 → 直播复盘 → 运营工作台 → 资料完整度 → 问题洞察」，同时保留了安全、测试、配置、数据库和 Docker 部署等工程实践内容，适合作为 AI 应用工程师方向的综合项目展示。旧版 CRM 客户管理 / 跟进分析 / 待跟进 / Agent 跟进助手相关代码、页面与测试已在 `chore: remove legacy CRM` 系列提交中移除，历史实现可查看 Git 历史。
