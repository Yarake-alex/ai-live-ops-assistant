import logging
import time
import traceback
from typing import Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

# Fast-token-estimate heuristics
FALLBACK_MESSAGE = (
    "AI 服务暂时不可用，请稍后重试。你可以稍后重试，或使用本地兜底内容继续演示。"
)
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
LIVE_SCRIPT_SECTION_TITLES = [
    "开场",
    "商品介绍",
    "核心卖点",
    "互动与异议处理",
    "促单收口",
]
LIVE_REVIEW_SECTION_TITLES = [
    "核心结论",
    "数据与现象",
    "做得好的部分",
    "主要问题",
    "下次行动清单",
]
PRODUCT_QA_REQUIRED_TITLE = "直接回答"
LIVE_COMMENT_REPLY_FIELD_LABELS = {
    "name": "商品名称",
    "price": "价格",
    "selling_points": "核心卖点",
    "target_audience": "适用人群",
    "pain_points": "用户痛点",
    "promotion": "优惠信息",
    "stock": "库存",
    "live_status": "直播状态",
    "notes": "备注",
}
LIVE_COMMENT_REPLY_COMMENT_LABEL = "观众评论"


def _estimate_tokens(text: str) -> int:
    """Rough estimate: Chinese 1-2 char/token, English ~4 char/token.

    Uses a blended rate of 2.5 chars per token — good enough for cost
    visibility, intentionally not a precise tokenizer.
    """
    if not text:
        return 0
    return max(1, round(len(text) / 2.5))


def _is_retryable_error(exc: Exception) -> bool:
    """True for transient network / 5xx errors that merit a retry.

    False for auth errors, bad requests, or other permanent failures.
    """
    msg = str(exc).lower()

    # openai library wraps HTTP errors; check status code
    code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if code is not None and code in RETRYABLE_HTTP_STATUS:
        return True
    if code is not None and code not in (0, None):
        return False  # 4xx, etc. — not retryable

    # Connection / timeout errors
    for keyword in (
        "timeout", "timed out", "connection", "connectionerror",
        "retryable", "server error", "internal server error",
        "service unavailable", "bad gateway", "gateway timeout",
        "too many requests", "rate limit",
    ):
        if keyword in msg:
            return True

    # Permanent errors
    for keyword in (
        "401", "403", "invalid api key", "unauthorized",
        "authentication", "incorrect api key",
    ):
        if keyword in msg:
            return False

    return True  # unknown errors → retry once (conservative)


def _write_usage_log(
    db: Optional[Session],
    *,
    user_id: Optional[int],
    feature: str,
    provider: str,
    model: str,
    prompt_chars: int,
    response_chars: int,
    status: str,
    error_message: Optional[str],
    duration_ms: int,
) -> None:
    """Persist an AiCallLog row.  Failure here is logged but never raised."""
    if not settings.LLM_ENABLE_USAGE_LOG or db is None:
        return
    try:
        # re-import within try so import failures don't propagate
        from app.models import AiCallLog

        log_entry = AiCallLog(
            user_id=user_id,
            feature=feature,
            provider=provider,
            model=model,
            prompt_chars=prompt_chars,
            response_chars=response_chars,
            estimated_prompt_tokens=_estimate_tokens("x" * prompt_chars) if prompt_chars else 0,
            estimated_response_tokens=_estimate_tokens("x" * response_chars) if response_chars else 0,
            status=status,
            error_message=(error_message[:500] if error_message else None),
            duration_ms=duration_ms,
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        try:
            if db is not None:
                db.rollback()
        except Exception:
            pass
        logger.warning("AiCallLog write failed (non-fatal): %s", traceback.format_exc())


def _safe_product_value(value, default: str = "未填写") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _format_script_context(script_context: dict | None) -> str:
    """把问题洞察上下文格式化为 prompt 片段；无数据时返回空字符串。"""
    if not script_context:
        return ""
    top = script_context.get("top_questions") or []
    unanswered = script_context.get("unanswered_questions") or []
    focus = script_context.get("script_focus") or []
    risk = script_context.get("risk_reminders") or []
    if not (top or unanswered or focus or risk):
        return ""

    lines = ["直播间问题洞察（来自真实观众/运营提问，如为空则跳过本节）："]
    if top:
        lines.append("- 高频问题：")
        for t in top[:5]:
            lines.append(f"  - “{t['question']}”（{t['count']} 次）")
    if focus:
        lines.append("- 话术主动讲解点（低风险高频问题）：" + "、".join(f["question"] for f in focus[:5]))
    if unanswered:
        lines.append("- 未覆盖问题（资料未明确）：")
        for u in unanswered[:5]:
            lines.append(f"  - “{u['question']}”")
    if risk:
        lines.append("- 风险问题：" + "、".join(r["question"] for r in risk[:3]))
    return "\n".join(lines) + "\n"


def build_live_script_prompt(product, script_context: dict | None = None) -> str:
    """Build a maintainable prompt for AI live commerce script generation."""
    sections = "\n".join(f"# {title}" for title in LIVE_SCRIPT_SECTION_TITLES)
    context_text = _format_script_context(script_context)
    return f"""
你是一个谨慎、专业的直播电商运营助手。请基于商品资料生成一份主播可直接口播的直播带货话术。

商品资料：
- 商品名称：{_safe_product_value(product.name)}
- 价格：{_safe_product_value(product.price)}
- 核心卖点：{_safe_product_value(product.selling_points)}
- 适用人群：{_safe_product_value(product.target_audience)}
- 用户痛点：{_safe_product_value(product.pain_points)}
- 优惠信息：{_safe_product_value(product.promotion)}
- 库存：{_safe_product_value(product.stock)}
- 直播状态：{_safe_product_value(product.live_status)}
- 备注：{_safe_product_value(product.notes)}

{context_text}
输出必须严格使用以下 Markdown 一级标题，按顺序各出现一次：
{sections}

格式与内容要求：
1. 每个一级标题下使用短段落、编号步骤或项目符号；内容面向主播可直接朗读或参考。
2. 不要在正文中重复标题；不要输出“以下是话术”等开场白、寒暄、免责声明或能力说明。
3. 只使用商品资料中已有的信息，不要编造不存在的功效、参数或承诺。
4. 不要涉及医疗、绝对化保证等高风险表达，也不要使用“全网最低”“百分百有效”“永久解决”等表述。
5. 商品资料不足时，在对应模块使用保守表达并提示需要补充的信息。
6. 如存在高频问题，可在「互动与异议处理」下用项目符号回应：低风险问题结合资料讲清；未覆盖问题明确“资料暂未明确，建议补充后再承诺”；风险问题只做谨慎引导。
7. 如无问题洞察数据，不要编造常见问题。
"""


_FALLBACK_QNA_CATEGORY_LABELS = {
    "price": "价格",
    "stock": "库存",
    "promotion": "优惠",
    "audience": "适用人群",
    "selling_points": "卖点",
}


def _build_fallback_qna_module(script_context: dict | None) -> str:
    """按问题上下文生成兜底话术的「直播间常问应答」模块；无数据时返回空字符串。"""
    if not script_context:
        return ""
    focus = script_context.get("script_focus") or []
    unanswered = script_context.get("unanswered_questions") or []
    risk = script_context.get("risk_reminders") or []
    if not (focus or unanswered or risk):
        return ""

    lines = ["", "", "## 直播间常问应答"]
    for f in focus[:3]:
        label = _FALLBACK_QNA_CATEGORY_LABELS.get(f["category"], "商品信息")
        lines.append(f"「{f['question']}」——建议结合商品资料的{label}信息直接讲清，以直播间实际信息为准。")
    for u in unanswered[:3]:
        lines.append(f"「{u['question']}」——该问题资料暂未明确，建议补充资料后再回答，不要临时编造。")
    for r in risk[:2]:
        lines.append(f"「{r['question']}」——涉及风险边界，只做谨慎引导，不做医疗、功效或绝对化承诺。")
    return "\n".join(lines)


def build_live_script_fallback(product, script_context: dict | None = None) -> str:
    """Local fallback script used when the LLM is unavailable."""
    name = _safe_product_value(product.name, "这款商品")
    price = _safe_product_value(product.price)
    selling_points = _safe_product_value(product.selling_points, "当前卖点资料还不完整，建议补充核心优势")
    target_audience = _safe_product_value(product.target_audience, "建议补充适用人群")
    pain_points = _safe_product_value(product.pain_points, "建议补充用户常见痛点")
    promotion = _safe_product_value(product.promotion, "暂无明确优惠信息")
    stock = _safe_product_value(product.stock)
    live_status = _safe_product_value(product.live_status)
    notes = _safe_product_value(product.notes, "暂无备注")

    qna_module = _build_fallback_qna_module(script_context)

    return f"""# 开场
欢迎大家来到直播间，今天给大家介绍的是{name}。这款商品当前直播状态是{live_status}，我们用已确认的信息讲清楚它适合谁、有什么特点。

# 商品介绍
- 当前价格：{price}元
- 当前库存：{stock}
- 适用人群：{target_audience}

# 核心卖点
{selling_points}。建议围绕已填写卖点讲解，不补充未确认的功效或参数。

# 互动与异议处理
- 如果你关注的问题是“{pain_points}”，可以结合自己的实际使用场景判断是否匹配。
- 大家也可以在评论区说说更看重价格、卖点、适用人群还是优惠力度。
- 对资料没有覆盖的信息，建议主播说明资料暂未明确后再补充，不做绝对保证。{qna_module}

# 促单收口
当前优惠信息是：{promotion}。确认需要的朋友可以查看直播间商品卡；补充备注为：{notes}。犹豫的朋友可以先收藏或留言补充问题，以页面实际信息为准。"""


def build_live_comment_reply_prompt(product, comment: str) -> str:
    """Build a maintainable prompt for AI live comment reply generation."""
    return f"""
你是一个谨慎、专业的直播电商主播助理。请针对直播间观众的一条评论，生成主播可以直接发出的简短回复。

商品资料：
- {LIVE_COMMENT_REPLY_FIELD_LABELS["name"]}：{_safe_product_value(product.name)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["price"]}：{_safe_product_value(product.price)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["selling_points"]}：{_safe_product_value(product.selling_points)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["target_audience"]}：{_safe_product_value(product.target_audience)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["pain_points"]}：{_safe_product_value(product.pain_points)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["promotion"]}：{_safe_product_value(product.promotion)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["stock"]}：{_safe_product_value(product.stock)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["live_status"]}：{_safe_product_value(product.live_status)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["notes"]}：{_safe_product_value(product.notes)}

{LIVE_COMMENT_REPLY_COMMENT_LABEL}：
{comment.strip()}

回复要求：
1. 简短自然，像主播直播时的口播语气，可直接念出。
2. 有转化意识：引导观众关注商品优势、优惠或下单入口。
3. 只使用商品资料中已有的信息，不编造功效、参数或承诺。
4. 不使用“全网最低”“百分百有效”“永久解决”等绝对化表述。
5. 如果评论问到商品资料中未包含的信息，坦诚说明暂未确认，不要编造。
6. 只输出回复内容本身，不要加“主播回复：”等前缀。
"""


def build_live_comment_reply_fallback(product, comment: str) -> str:
    """Local fallback reply used when the LLM is unavailable."""
    name = _safe_product_value(product.name, "这款商品")
    price = _safe_product_value(product.price)
    promotion = _safe_product_value(product.promotion, "当前场次的优惠以页面实际活动为准")
    target_audience = _safe_product_value(product.target_audience, "建议在商品详情确认适用人群")
    selling_points = _safe_product_value(product.selling_points, "商品卖点资料还不完整")

    comment_lower = comment.strip()
    if "优惠" in comment_lower or "便宜" in comment_lower or "价" in comment_lower:
        return f"亲，{name} 当前价格 {price} 元，优惠信息是：{promotion}。有活动我们会在直播间及时说，可以先看看商品卡～"
    if "适合" in comment_lower or "能用" in comment_lower or "可以" in comment_lower:
        return f"亲，{name} 的适用人群是：{target_audience}，可以对照自己的情况看看是否合适，拿不准也可以再问我～"
    if "质量" in comment_lower or "怎么样" in comment_lower:
        return f"亲，{name} 的核心卖点是：{selling_points}。我们只介绍资料里确认过的信息，建议结合自己的需求判断～"
    return f"亲，感谢关注！{name} 价格 {price} 元，优惠方面是：{promotion}。想看更多细节可以戳商品卡，也可以在评论区继续问我～"


def build_product_rag_prompt(product, question: str, retrieved_chunks) -> str:
    """Build a prompt for product knowledge base QA (直播商品资料问答)。"""
    references = []
    for idx, chunk in enumerate(retrieved_chunks, start=1):
        references.append(
            f"【资料{idx}】文件名：{chunk.filename}；片段序号：{chunk.chunk_index}\n{chunk.content}"
        )

    context = "\n\n".join(references)

    return f"""
你是一个谨慎、专业的直播电商商品资料问答助手。
请严格根据下面的“商品知识库资料”并参考商品基础资料回答用户问题。

商品资料：
- {LIVE_COMMENT_REPLY_FIELD_LABELS["name"]}：{_safe_product_value(product.name)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["price"]}：{_safe_product_value(product.price)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["selling_points"]}：{_safe_product_value(product.selling_points)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["target_audience"]}：{_safe_product_value(product.target_audience)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["pain_points"]}：{_safe_product_value(product.pain_points)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["promotion"]}：{_safe_product_value(product.promotion)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["stock"]}：{_safe_product_value(product.stock)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["live_status"]}：{_safe_product_value(product.live_status)}
- {LIVE_COMMENT_REPLY_FIELD_LABELS["notes"]}：{_safe_product_value(product.notes)}

输出格式：
1. 必须先输出 `# 直接回答`，用简洁自然语言直接回答，不重复用户问题。
2. 有明确资料依据时，再输出 `## 依据资料` 并用项目符号说明依据。
3. 适合主播口播时，再输出 `## 建议话术`。
4. 有边界、风险或资料未明确内容时，再输出 `## 注意事项`；没有资料依据时必须明确说明，不得编造资料来源。
5. 不要输出寒暄、免责声明、能力说明或“以下是回答”等无意义开场白。
6. 不要原样复制 Markdown 表格；资料来源是表格时改写为分点说明。
7. 不使用“全网最低”“百分百有效”“永久解决”等绝对化表述。

用户问题：
{question}

商品知识库资料：
{context}
"""


def build_live_review_prompt(
    product,
    *,
    script_count: int,
    reply_count: int,
    knowledge_docs: int,
    recent_comments: str,
) -> str:
    """Build a maintainable prompt for AI live review (直播复盘) generation."""
    sections = "\n".join(f"# {title}" for title in LIVE_REVIEW_SECTION_TITLES)
    return f"""
你是一个谨慎、专业的直播电商运营复盘助手。请基于当前商品资料和已有运营数据，生成一份直播复盘。

商品资料：
- 商品名称：{_safe_product_value(product.name)}
- 价格：{_safe_product_value(product.price)}
- 核心卖点：{_safe_product_value(product.selling_points)}
- 适用人群：{_safe_product_value(product.target_audience)}
- 用户痛点：{_safe_product_value(product.pain_points)}
- 优惠信息：{_safe_product_value(product.promotion)}
- 库存：{_safe_product_value(product.stock)}
- 直播状态：{_safe_product_value(product.live_status)}
- 备注：{_safe_product_value(product.notes)}

运营数据：
- 已生成直播话术数：{script_count}
- 模拟评论回复数：{reply_count}
- 商品知识库文档数：{knowledge_docs}
- 近期观众评论（最多10条）：
{recent_comments or "暂无评论记录"}

输出必须严格使用以下 Markdown 一级标题，按顺序各出现一次：
{sections}

要求：
1. 「下次行动清单」必须使用编号列表，结论与建议具体、可执行。
2. 没有足够数据时明确写“暂无足够数据”，但仍给出合理的下一步建议。
3. 只使用上面给出的资料与数据，不编造直播场次、销量、GMV、转化率、观看人数等不存在的指标。
4. 评论样本较少时明确说明“当前评论样本较少”；资料未覆盖内容说明“暂未明确”。
5. 不输出寒暄、免责声明、能力说明或“以下是复盘”等无意义开场白。
"""


def build_live_review_fallback(
    product,
    *,
    script_count: int,
    reply_count: int,
    knowledge_docs: int,
    recent_comments: str,
) -> str:
    """Local fallback review used when the LLM is unavailable."""
    name = _safe_product_value(product.name, "这款商品")
    selling_points = _safe_product_value(product.selling_points, "建议补充核心卖点")
    target_audience = _safe_product_value(product.target_audience, "建议补充适用人群")
    pain_points = _safe_product_value(product.pain_points, "建议补充用户痛点")
    promotion = _safe_product_value(product.promotion, "暂无明确优惠信息")

    # 缺失字段判断基于原始字段，避免 _safe_product_value 的默认文案干扰判断
    missing = []
    if not str(product.selling_points or "").strip():
        missing.append("核心卖点")
    if not str(product.target_audience or "").strip():
        missing.append("适用人群")
    if not str(product.pain_points or "").strip():
        missing.append("用户痛点")
    missing_text = "、".join(missing) if missing else "无明显缺失"

    if recent_comments.strip():
        comments_text = recent_comments.strip()
        conclusion = "当前已有评论与回复记录，可据此继续补充标准答疑与话术。"
        data_text = f"- 已生成直播话术：{script_count} 份\n- 模拟评论回复：{reply_count} 条\n- 商品知识库文档：{knowledge_docs} 份\n- 近期评论与回复：\n{comments_text}"
    else:
        conclusion = "暂无足够数据，当前评论样本较少；建议先积累更多评论和直播记录后再复盘。"
        data_text = f"- 已生成直播话术：{script_count} 份\n- 模拟评论回复：{reply_count} 条\n- 商品知识库文档：{knowledge_docs} 份\n- 近期评论与回复：暂无评论记录"

    return f"""# 核心结论
{conclusion}

# 数据与现象
{data_text}

# 做得好的部分
- 已围绕核心卖点「{selling_points}」建立基础话术参考。
- 已记录的资料与回复可继续作为后续答疑依据。

# 主要问题
- 商品资料缺失项：{missing_text}。
- 质量、效果等资料未明确的内容不做推断，建议以商品页信息为准，不夸大承诺。

# 下次行动清单
1. 优先补齐资料完整度中的缺失字段：{missing_text}。
2. 围绕用户痛点「{pain_points}」准备主播话术，并在评论回复中主动引导。
3. 若知识库文档不足（当前 {knowledge_docs} 份），上传商品手册、FAQ 等资料辅助答疑。
4. 复盘只依据已记录数据（话术 {script_count} 份、评论回复 {reply_count} 条），不推断未记录的直播指标。"""


def resolve_llm_provider_model() -> tuple[str, str]:
    """返回 call_llm 实际会使用的 (provider, model) 组合。

    与 call_llm 内部的 mock / 真实 API 分支判断保持一致，供生成记录的
    provider/model 字段复用，避免两处逻辑漂移。
    """
    if settings.LLM_PROVIDER == "openai_compatible" and settings.OPENAI_API_KEY:
        return "openai_compatible", settings.OPENAI_MODEL
    return "mock", "mock"


def call_llm(
    prompt: str,
    *,
    feature: str = "unknown",
    user_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> str:
    """Call the LLM with timeout, retries, fallback, and usage logging.

    Old callers that use ``call_llm(prompt)`` continue to work unchanged.
    """
    t0 = time.perf_counter()
    max_chars = settings.LLM_MAX_PROMPT_CHARS
    provider = "mock"
    model = ""
    status = "error"  # default; set to "success" only on actual success
    error_message: Optional[str] = None
    response_text = ""

    # ── Prompt truncation ──
    if len(prompt) > max_chars:
        truncated = prompt[-max_chars:]  # keep the tail (newest context)
        logger.warning(
            "Prompt truncated from %d to %d chars (feature=%s, user=%s)",
            len(prompt), max_chars, feature, user_id,
        )
        prompt = truncated

    prompt_chars = len(prompt)

    # ── Mock path ──
    if settings.LLM_PROVIDER != "openai_compatible" or not settings.OPENAI_API_KEY:
        provider, model = resolve_llm_provider_model()
        try:
            response_text = mock_llm_response(prompt, feature=feature)
            status = "success"
        except Exception:
            status = "error"
            error_message = "mock LLM returned an unexpected error"
            response_text = FALLBACK_MESSAGE
        duration_ms = round((time.perf_counter() - t0) * 1000)
        try:
            _write_usage_log(
                db, user_id=user_id, feature=feature, provider=provider,
                model=model, prompt_chars=prompt_chars,
                response_chars=len(response_text), status=status,
                error_message=error_message, duration_ms=duration_ms,
            )
        except Exception:
            logger.warning("Usage log write failed (non-fatal): %s", traceback.format_exc())
        return response_text

    # ── Real API path ──
    provider, model = resolve_llm_provider_model()

    import httpx

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        timeout=httpx.Timeout(settings.LLM_TIMEOUT_SECONDS),
        max_retries=0,  # we handle retries ourselves for smart classification
    )

    last_exc: Optional[Exception] = None

    for attempt in range(1 + settings.LLM_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的直播电商运营助手，回答要具体、可执行、适合直播运营人员使用。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_COMPLETION_TOKENS,
            )
            response_text = response.choices[0].message.content or ""
            status = "success"
            error_message = None
            break  # success — exit retry loop
        except Exception as exc:
            last_exc = exc
            can_retry = _is_retryable_error(exc) and (attempt < settings.LLM_MAX_RETRIES)
            logger.warning(
                "LLM call failed (attempt %d/%d, feature=%s, user=%s): %s",
                attempt + 1, 1 + settings.LLM_MAX_RETRIES, feature, user_id, exc,
            )
            if can_retry:
                time.sleep(min(2 ** attempt, 4))  # exponential backoff capped at 4s
                continue
            break

    if status != "success":
        # API call failed — record the error, then deliver the fallback.
        if not error_message and last_exc is not None:
            error_message = str(last_exc)[:500]
        if not response_text:
            response_text = FALLBACK_MESSAGE
        status = "fallback"

    duration_ms = round((time.perf_counter() - t0) * 1000)
    try:
        _write_usage_log(
            db, user_id=user_id, feature=feature, provider=provider,
            model=model, prompt_chars=prompt_chars,
            response_chars=len(response_text), status=status,
            error_message=error_message, duration_ms=duration_ms,
        )
    except Exception:
        logger.warning("Usage log write failed (non-fatal): %s", traceback.format_exc())
    return response_text


def _extract_live_comment_reply_fields(prompt: str) -> dict[str, str]:
    """从评论回复 prompt 中解析商品字段与观众评论。

    简单按行匹配「字段名：值」格式（兼容「- 字段名：值」），不做复杂解析；
    未找到的字段返回空字符串。观众评论的正文在标题行的下一行。
    """
    labels = {label: key for key, label in LIVE_COMMENT_REPLY_FIELD_LABELS.items()}
    labels[LIVE_COMMENT_REPLY_COMMENT_LABEL] = "comment"
    fields: dict[str, str] = {}
    lines = prompt.splitlines()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("- "):
            line = line[2:]
        for label, key in labels.items():
            prefix = label + "："
            if line.startswith(prefix):
                fields[key] = line[len(prefix):].strip()
                if key == "comment" and not fields[key]:
                    # 评论正文在「观众评论：」标题的下一行
                    for nxt in lines[i + 1:]:
                        candidate = nxt.strip()
                        if candidate:
                            fields[key] = candidate
                            break
                break
    return fields


def _mock_context_value(value: str) -> str:
    """把 prompt 中的字段值转成可用值；「未填写」等占位视为缺失。"""
    value = (value or "").strip()
    if not value or value == "未填写":
        return ""
    return value


def mock_llm_response(prompt: str, feature: str = "unknown") -> str:
    # 直播话术通过显式 feature 分发，不再依赖 prompt 关键词
    if feature == "live_script_generation":
        return """# 开场
欢迎来到直播间，今天这款商品适合认真对比、想快速抓住重点的朋友。

# 商品介绍
- 会围绕价格、卖点、适用人群和优惠信息讲清楚已确认内容。
- 未确认的信息以商品页实际展示为准。

# 核心卖点
建议围绕资料中已填写的核心卖点展开，用真实信息说明它为什么值得关注，不额外夸大未确认的效果。

# 互动与异议处理
- 大家可以在评论区说说最关心价格、库存、适用人群、优惠还是自己的使用场景。
- 对是否适合自己有疑问的朋友，可以先对照适用人群和核心卖点；资料未覆盖的情况，建议补充问题后再判断。

# 促单收口
确认需要的朋友可以查看商品卡；下单前也可以继续留言确认关键信息。"""

    if feature == "product_rag_ask":
        return """# 直接回答
根据已上传的商品资料，建议围绕商品的核心卖点、适用人群和优惠信息回答。

## 依据资料
- 当前回答仅参考已上传的商品资料。

## 注意事项
资料中未明确提到的内容应补充资料后再回答，不要编造资料来源。"""

    if feature == "live_review":
        return """# 核心结论
暂无足够数据，当前评论样本较少；建议先积累更多评论和直播记录后再复盘。

# 数据与现象
- 当前仅依据已记录的商品资料、话术和评论回复进行判断。

# 做得好的部分
- 已具备围绕商品资料开展话术和答疑的基础条件。

# 主要问题
- 核心卖点、适用人群、用户痛点、优惠信息等资料可能仍需补齐。

# 下次行动清单
1. 补齐缺失的商品资料字段。
2. 针对高频评论问题整理标准回复。
3. 上传商品手册、FAQ 等资料到商品知识库，提升答疑准确度。"""

    if feature == "live_comment_reply":
        # 从 prompt 中解析商品字段与评论，生成 1-3 句结合商品信息的主播口吻回复
        f = _extract_live_comment_reply_fields(prompt)
        name = _mock_context_value(f.get("name", ""))
        price = _mock_context_value(f.get("price", ""))
        promotion = _mock_context_value(f.get("promotion", ""))
        audience = _mock_context_value(f.get("target_audience", ""))
        selling = _mock_context_value(f.get("selling_points", ""))
        pain = _mock_context_value(f.get("pain_points", ""))
        comment = f.get("comment", "").strip()

        if not name:
            return "亲，这款商品的具体信息以商品页为准，价格、优惠和适用人群都可以在商品卡里确认，有疑问继续问我～"

        # 第 1 句：名称 + 价格 + 优惠（缺失时不编造）
        s1 = f"亲，这款是{name}" + (f"，价格{price}元" if price else "") + (
            f"，优惠是：{promotion}" if promotion else ""
        ) + "。"

        # 第 2 句：适用人群 / 核心卖点 / 用户痛点（有则说，缺失则以商品页为准）
        s2_parts = []
        if audience:
            s2_parts.append(f"适用人群是：{audience}")
        if selling:
            s2_parts.append(f"核心卖点是：{selling}")
        if pain:
            s2_parts.append(f"主要针对的痛点是：{pain}")
        s2 = "，".join(s2_parts) + "。" if s2_parts else "具体信息以商品页为准。"

        # 第 3 句：评论回答方向 + 转化收尾；质量/效果/敏感肌等问题保持保守表达
        s3 = ""
        if any(k in comment for k in ("质量", "效果", "敏感", "怎么样")):
            s3 = "关于质量和效果，我们只介绍资料里确认过的信息，不夸大承诺；"
        s3 += "喜欢的朋友可以点商品卡看看，拿不准的继续问我～"

        return s1 + s2 + s3

    if "知识库资料" in prompt or "参考资料" in prompt:
        return """# 直接回答
根据已上传资料，当前问题可以结合资料中的关键信息回答。

## 依据资料
- 当前回答基于已上传的资料片段。

## 注意事项
资料中未明确提到的内容应补充资料后再回答，不要编造资料来源。"""

    return "当前为 mock 模式，如需真实 AI 回答，请在 .env 中配置 DeepSeek API。"
