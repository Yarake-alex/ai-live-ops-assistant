# AI 直播运营助手 V4 设计说明

> V4 定位：**问题驱动的资料补齐与话术优化**
> ✅ **V4 已落地**：本设计全部能力已按阶段实现并验证通过（详见文末落地记录）。

---

## 1. 背景与目标

### 背景

当前直播运营路线已完成：

- **V1 直播运营 MVP**：商品资料、商品资料文档问答、开播话术、评论助手、直播复盘、运营工作台。
- **V2 资料检索增强 + 开播准备**：商品资料语义检索（真实 Embedding + 本地 Chroma，自动降级基础检索）、
  资料完整度评分（`GET /products/{id}/readiness`，12 项确定性规则）、开播准备入口。
- **V3 问题洞察 + 本地快答**：商品问题记录（`product_question_logs`）、9 类关键词分类（risk 优先）、
  低风险本地规则快答、商品级问题洞察接口（`GET /products/{id}/question-insights`）与前端面板。

### 目标

V2 让系统"知道资料缺什么"，V3 让系统"看见用户问什么"，V4 把两者串起来——
从"看见问题"推进到**"知道该补什么、该讲什么"**：

```
用户常问什么 → 哪些资料没覆盖 → 应该补哪些 FAQ → 话术应该强化哪些点 → 开播前要注意什么
```

V4 不做复杂大屏，也不做任务系统；产出的是**运营人员可执行的轻量动作建议**。

## 2. 范围内

- 资料补齐建议（material_gap）：哪些资料该补、补什么方向
- FAQ 补充建议（faq_candidate）：哪些高频问题值得沉淀为 FAQ（**只建议，不写入文档**）
- 话术优化建议（script_focus）：直播间需要主动讲清楚的点
- 开播准备联动建议（risk_reminder / 完整性提醒）：开播前要注意什么
- **规则优先**：全部建议由确定性规则生成，不依赖 LLM；必要时后续版本再考虑 LLM 参与

## 3. 范围外（明确不做）

- 自动修改商品资料
- 自动生成并保存 FAQ 文档
- 复杂 BI 大屏、趋势图、词云
- 自动日报
- 多租户、复杂 RBAC、部门/主管/人事权限
- 真实直播平台接入
- Redis、Celery、Kubernetes
- 旧 CRM（已下线，不恢复）

## 4. 数据来源（全部复用，零新表、零新依赖）

| 数据 | 来源 |
|---|---|
| 问题日志 | `product_question_logs`（source/category/normalized_question/answer_mode/was_answered） |
| 问题统计 | `GET /products/{id}/question-insights`（top_questions / category_counts / recent_questions / unanswered_questions） |
| 资料完整度 | `GET /products/{id}/readiness`（score / missing_items / suggestions） |
| 商品基础字段 | `Product`（价格、库存、卖点、人群、痛点、优惠、备注） |
| 商品资料文档 | 文档列表与文件名（FAQ / 售后 / 风险边界等文件名识别规则与 V2 完整度一致） |

不新增复杂数据源；所有统计沿用 V3 的 user_id + product_id 双重隔离口径。

## 5. 建议类型设计

| 类型 | 触发条件 | 展示文案 | 优先级 | 人工处理 | 不自动做什么 |
|---|---|---|---|---|---|
| `material_gap` | 某分类高频或未覆盖问题多，且对应资料维度未覆盖（按 V2 完整度维度判定） | 「建议补充风险边界资料」「建议补充售后规则」 | high（风险/未覆盖）/ normal | 是（运营手动补资料） | 不自动写入资料文档 |
| `faq_candidate` | `top_questions` 中重复问题 `count >= 2`（且分类非 other） | 「高频问题"多少钱"（8 次）建议沉淀为 FAQ」 | normal | 是（运营决定是否沉淀） | 不自动生成并保存 FAQ 文档 |
| `script_focus` | 高频问题（含已被 `local_rule` 回答的低风险问题）与未覆盖问题 | 「直播间可主动讲清价格/优惠」 | normal | 否（仅提示，话术增强在阶段 5 落地） | 不改变话术接口响应结构 |
| `risk_reminder` | `risk` 分类计数 > 0 或完整度风险边界维度未命中 | 「开播前确认风险边界，避免承诺治疗功效」 | high | 是（运营确认） | 不做审批流/任务分配 |

每条建议统一结构：

```json
{
  "type": "material_gap",
  "priority": "high",
  "title": "建议补充风险边界资料",
  "detail": "近期多次出现孕妇/过敏相关问题，当前资料未覆盖明确边界。",
  "source_questions": ["孕妇能不能用"],
  "action_label": "补充风险说明"
}
```

## 6. 建议生成规则（确定性，不依赖 LLM）

在 `app/question_insights.py` 扩展纯函数 `build_ops_suggestions(...)`，规则如下：

1. **risk 未覆盖或高频 > 0** → `material_gap`（high）：「建议补充风险边界 / 禁用话术」，source_questions 取 risk 分类的问题样本；
   同时产生 `risk_reminder`（high）：「开播前确认风险边界」。
2. **after_sales 高频或未覆盖** → `material_gap`：「建议补充售后规则 / 退换政策」。
3. **usage 高频或未覆盖** → `material_gap`：「建议补充使用方法 / 注意事项」。
4. **audience 高频或未覆盖** → `material_gap`：「建议补充适用 / 不适用人群」。
5. **top_questions 中 `count >= 2` 且分类非 other** → `faq_candidate`：question / category / count / 建议沉淀方向。
6. **资料完整度 < 80** → `material_gap`（normal）：「开播前建议先补资料」，detail 引用完整度 missing_items。
7. **低风险且已被 `local_rule` 回答的问题**（price/stock/promotion 等）→ 不产补资料建议，转为 `script_focus`：
   「直播间可主动讲清价格/库存/优惠」，作为话术主动讲解点。
8. **未覆盖问题 Top 5** → 进入对应分类的 `material_gap` 或 `faq_candidate` 的 `source_questions`，不单独成条。
9. 无任何问题日志时 → 返回空建议列表 + 温和空态（summary 全 0）。

## 7. 建议接口草案（本阶段不实现）

新增：`GET /products/{id}/ops-suggestions`

```json
{
  "summary": {
    "total": 5,
    "high_priority": 2,
    "needs_material_update": true
  },
  "suggestions": [
    {
      "type": "material_gap",
      "priority": "high",
      "title": "建议补充风险边界资料",
      "detail": "近期多次出现孕妇/过敏相关问题，当前资料未覆盖明确边界。",
      "source_questions": ["孕妇能不能用"],
      "action_label": "补充风险说明"
    }
  ]
}
```

约束：

- 只按当前 `user_id + product_id` 统计，普通 user 只能看自己的商品，admin 不默认跨用户查看业务资料；
- 归属校验同 readiness：`get_current_user + get_product_for_user`；
- 不新增任务分配系统（无负责人/截止时间/提醒/审批）；
- 接口为**加性新增**，不改动任何现有接口与返回结构。

## 8. 前端展示草案（阶段 4 落地）

- 位置：商品资料页「问题洞察」Tab 内新增「💡 运营建议」轻量卡片（或置于开播准备概览下方）。
- 展示：summary 徽标（总建议数 / 高优先级数）+ 建议列表（title / detail / source_questions / action_label）。
- 复用现有 card/tag/list 样式；不引入图表库；**不暴露技术词**（不出现 answer_mode / local_rule / Embedding / 向量 等），
  分类用运营语言标签（价格/库存/优惠/适用人群/卖点/使用方法/售后/风险边界/其他）。
- 选中商品 / 提问 / 评论生成后随问题洞察一并刷新；接口失败显示温和提示，不影响现有功能。

## 9. 验收标准

**后端**
- 能基于已有问题日志 + 完整度生成建议，且**不调用 LLM 也可工作**（纯规则）。
- 没有问题日志时返回空建议或温和空态。
- 不跨用户、不跨商品；他人访问 404。

**前端**
- 能看到运营建议，且能看出建议来源于哪些高频/未覆盖问题（source_questions）。
- 文案为运营语言；不影响现有问题洞察、资料问答、话术、复盘。

**测试**
- material_gap / faq_candidate / script_focus / risk_reminder 规则测试
- 用户隔离、商品隔离、空数据测试
- 现有 360 个测试继续通过（无回归）

## 10. 分阶段落地顺序（实际记录）

| 阶段 | 内容 | 状态 / 提交 |
|---|---|---|
| 1 | V4 设计说明 | ✅ `acf9987` |
| 2 | 后端建议生成 helper + `ops-suggestions` 接口（测试并入阶段 2，测试文件为 `tests/test_question_insights.py`） | ✅ `103c2bf` |
| 4 | 前端运营建议卡片 | ✅ `331a89e` |
| 5 | 话术生成增强（prompt + 兜底「直播间常问应答」） | ✅ `da220a0` |
| 6 | 文档同步（README / demo-guide / mvp-scope 同步 V4 说明） | 待提交 |

最终测试结果：**全量 377 passed, 1 warning**（warning 为既有 fixture 弃用提示）。

