# AI 直播运营助手 V3 设计说明（定稿）

> V3 定位：**直播问题洞察 + 高频问题本地快答**
> 本文档为 V3 最终设计记录：已按 A→E 阶段全部落地并通过验证。

---

## 1. V3 背景与目标

### 背景

- V2 已完成：商品资料语义检索（真实 Embedding + 本地 Chroma，自动降级基础检索）、资料完整度评分、开播准备入口。
- V2 的缺口：系统"能回答"但**不沉淀问题**——观众/运营问了什么、哪些问题重复、哪些问题资料没覆盖，随会话消失；复盘与话术也无从参考真实高频问题。

### 目标

1. **问题数据沉淀**：商品问答与评论助手输入落轻量日志（只记问题，不记回答内容）。
2. **重复问题降本提速**：价格/库存/优惠/人群/卖点等低风险、确定性信息由商品字段本地快答，不调 LLM、不走向量。
3. **反向提示补资料**：未覆盖问题进入统计，运营据此补商品资料文档。
4. **为复盘/话术提供素材**（本版仅展示，不改复盘链路）。

### 非目标

不是复杂数据大屏、不是直播平台接入、不是任务系统。

## 2. V3 范围

**范围内**：问题记录（商品问答 + 评论助手）、关键词规则分类（9 类）、低风险本地快答（5 类）、
商品级问题洞察接口、前端轻量问题洞察面板。

**范围外**：真实直播平台接入、WebSocket 实时弹幕、复杂 BI 大屏、自动运营日报、语音识别、
多租户 / 部门权限 / 复杂 RBAC、Redis / Celery / Kubernetes、混合检索所有资料
（商品问答仍只查当前商品资料文档）。

## 3. 数据模型

新增表 `product_question_logs`（模型 `ProductQuestionLog`）：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `user_id` / `product_id` | 外键 + 索引，**双重隔离**，admin 不默认跨用户看业务问题数据 |
| `source` | `product_knowledge_ask` / `comment_reply` |
| `question` | 原始输入，截断 500 字符 |
| `normalized_question` | 小写 + 去标点空白 + 截断（无分词/NLP） |
| `category` | 9 类之一，见第 4 节 |
| `answer_mode` | `local_rule` / `product_knowledge` / `llm` / `fallback` / `no_match` |
| `was_answered` | 默认 true；未命中或生成失败为 false |
| `created_at` | 默认当前时间 |

- 不记录完整回答内容、不记录任何敏感信息；建表沿用 `upgrade_database` 幂等模式 + 组合索引 `(user_id, product_id)`。
- 写入为 **best-effort**：失败仅 `logger.warning` + rollback，不影响问答/评论主流程。

## 4. 问题分类（纯关键词规则，不调 LLM、不新增 NLP 依赖）

按优先级顺序匹配、命中即停——**risk 优先级最高**，避免「孕妇/儿童/过敏/禁忌/不能用」被误判为低风险人群问题：

| category | 关键词 | 中文标签 |
|---|---|---|
| risk | 孕妇、儿童、小孩、过敏、副作用、禁忌、不能用、不适合、刺激 | 风险边界 |
| after_sales | 售后、退换、退货、换货、保修、坏了 | 售后 |
| price | 多少钱、价格、贵不贵、几块、多少米 | 价格 |
| stock | 库存、还有吗、现货、缺货 | 库存 |
| promotion | 优惠、活动、券、满减、买一送一 | 优惠 |
| audience | 适合谁、什么人用、什么人、敏感肌、人群 | 适用人群 |
| selling_points | 好在哪、优势、特点、卖点 | 卖点 |
| usage | 怎么用、用法、步骤、一天几次、用量 | 使用方法 |
| other | 未命中 | 其他 |

## 5. 本地快答（`build_local_product_answer`）

仅支持 5 类低风险确定性字段，模板只转述字段值、不编造：

| category | 字段要求 | 弱提示 |
|---|---|---|
| price | `price > 0` | 以直播间实际展示为准 |
| stock | `stock > 0` | 以实际下单页面为准 |
| promotion | 非空 | 以直播间说明为准 |
| audience | 非空 | 建议结合商品资料或咨询客服 |
| selling_points | 非空 | — |

规则：
- 命中且字段非空 → 直接返回 `{answer, sources: []}`，日志 `answer_mode=local_rule, was_answered=true`；
  **不调 LLM、不走向量**。
- 字段为空 → 不强答，继续走商品资料语义检索链路。
- risk / after_sales / usage / other → 一律不本地快答。

## 6. 问答链路

`POST /products/{id}/knowledge/ask`：

1. 归属校验（`get_current_user` + `get_product_for_user`）
2. 分类 + 本地快答 → 命中即返回（`local_rule`）
3. 未命中 → 商品资料向量检索 + 四层降级（V2 链路不变）：
   - 检索命中 → `product_knowledge` / LLM 生成
   - LLM 兜底 → `fallback`（计为已应答，用户拿到可用提示）
   - 无资料 / 无检索结果 → `no_match`、`was_answered=false`
4. 所有路径均落 `product_question_logs`（best-effort）

`POST /products/{id}/comment-replies`：仅追加输入评论记录（`source=comment_reply`，answer_mode 映射
success→llm / fallback→fallback / failed→no_match），**生成逻辑不变**。

## 7. 问题洞察接口

`GET /products/{product_id}/question-insights`：

```json
{
  "top_questions":      [{"question": "多少钱", "count": 8, "category": "price"}],
  "category_counts":    [{"category": "price", "label": "价格", "count": 12}],
  "recent_questions":   [{"question": "...", "category": "...", "answer_mode": "...",
                          "was_answered": true, "created_at": "..."}],
  "unanswered_questions": [{"question": "孕妇能不能用", "category": "risk", "count": 3}]
}
```

- 只统计当前用户 + 当前商品；`category_counts` 9 类全量返回（无数据 count=0）；
  `top_questions`/`unanswered_questions` 按归一化问题分组 Top 5，question/category 取组内最新一条；
  `recent_questions` 最近 10 条。
- Python 聚合（MVP 数据量），不做分页/导出。

## 8. 前端问题洞察面板

商品资料页「资料完整度」下方新增「❓ 问题洞察」卡片：高频问题 / 分类统计 / 未覆盖问题（建议补充资料）/
最近问题（已回答/未覆盖徽标）；空态与失败态友好提示；不引入图表库、不展示技术词（含 answer_mode）；
选中商品 / 提问 / 评论生成后自动刷新。

## 9. 测试

- `tests/test_question_insights.py` 35 个用例：归一化、9 类分类与 risk 优先、日志写入（问答/评论助手/
  no_match）、best-effort、本地快答 5 类命中与字段为空不强答、高风险不快答、**monkeypatch 证明零 LLM
  调用与零向量检索**、洞察统计（空态/聚合/分类/最近/未命中）与 user/product 隔离、未登录 401。
- 全量 pytest 360 passed（1 个既有 fixture 弃用 warning）。

## 10. 落地记录

| 阶段 | 内容 | 提交 |
|---|---|---|
| A | 问题记录表 + 分类规则 | `3123de1` |
| B | 本地快答 | `59b4d29` |
| C | 问题洞察接口 | `48ffb2e` |
| D | 前端轻量面板 | `ea8b768` |
| E | 文档同步与设计定稿 | 本文档 |

## 11. 风险与约束（落地时已遵守）

- 本地快答不过度自信：只转述字段值，价格/库存/优惠带"以实际为准"弱提示。
- 高风险问题绝不靠字段硬答：risk 分类优先，永远走资料检索。
- 问题归一化保持简单：小写 + 去标点，不做分词。
- 不把洞察做成 BI 大屏：单商品 Top N 轻量面板。
- 不影响 V2 语义检索：快答只是前置短路，未命中无缝回到原链路。
- 不记录敏感信息：只记问题文本，不记回答全文与任何身份信息。
