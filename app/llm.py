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
    "AI 服务暂时不可用，请稍后重试。你仍可以先记录本次跟进内容。"
)
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
LIVE_SCRIPT_SECTION_TITLES = [
    "开场引入",
    "商品卖点讲解",
    "用户痛点刺激",
    "互动提问",
    "优惠逼单",
    "异议回应",
    "结尾转化",
]
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


def build_customer_context(customer, followups):
    records = "\n".join(
        [
            f"- 时间：{f.created_at.strftime('%Y-%m-%d %H:%M')}；内容：{f.content}；下一步：{f.next_action or '暂无'}"
            for f in followups
        ]
    ) or "暂无跟进记录"

    return f"""
客户姓名：{customer.name}
公司名称：{customer.company}
行业：{customer.industry or '未知'}
客户等级：{customer.level or '未设置'}
意向程度：{customer.intention or '未设置'}
合作状态：{customer.cooperation_status or '未设置'}
电话：{customer.phone or '未填写'}
邮箱：{customer.email or '未填写'}

历史跟进记录：
{records}
"""


def _safe_product_value(value, default: str = "未填写") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def build_live_script_prompt(product) -> str:
    """Build a maintainable prompt for AI live commerce script generation."""
    sections = "\n".join(f"- {title}" for title in LIVE_SCRIPT_SECTION_TITLES)
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

必须输出以下七个模块，每个模块都要有清晰标题：
{sections}

要求：
1. 面向直播电商主播，语言自然，适合直接口播。
2. 只使用商品资料中已有的信息，不要编造不存在的功效、参数或承诺。
3. 不要涉及医疗、绝对化保证等高风险表达。
4. 不要使用“全网最低”“百分百有效”“永久解决”等绝对化表述。
5. 如果商品资料不足，请在对应模块提醒补充信息，并给出保守表达。
"""


def build_live_script_fallback(product) -> str:
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

    return f"""开场引入
欢迎大家来到直播间，今天给大家介绍的是{name}。这款商品当前直播状态是{live_status}，如果你正在对比同类产品，可以先听我用一分钟讲清楚它适合谁、解决什么问题。

商品卖点讲解
这款商品的核心卖点是：{selling_points}。当前价格为{price}元，库存为{stock}。建议主播围绕已填写卖点讲解，不补充未确认的功效或参数。

用户痛点刺激
如果你平时遇到的问题是：{pain_points}，可以重点关注这款商品是否匹配你的使用场景。这里不做夸大承诺，建议结合自己的实际需求判断。

互动提问
大家可以在评论区告诉我：你更看重价格、卖点、适用人群，还是优惠力度？如果你属于{target_audience}，也可以直接打在公屏上，我帮你一起看是否适合。

优惠逼单
当前优惠信息是：{promotion}。如果你已经确认需要，可以优先关注本场直播间的下单入口；如果优惠信息还不完整，建议主播先提示以页面实际活动为准。

异议回应
如果你担心不适合自己，建议先看商品资料里的适用人群：{target_audience}。如果还不确定，可以先留言说明你的使用场景，主播根据已知信息做保守建议，不做绝对保证。

结尾转化
最后再帮大家总结一下：{name} 适合关注「{selling_points}」的用户，补充备注为：{notes}。确认需要的朋友可以查看直播间商品卡，犹豫的朋友可以先收藏或留言补充问题。"""


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
                        "content": "你是一个专业的 ToB 销售客户跟进助手，回答要具体、可执行、适合销售人员使用。",
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
        return """开场引入
欢迎来到直播间，今天这款商品适合正在认真对比、想快速抓住重点的朋友。先别急着划走，我会按价格、卖点、适用人群和优惠信息帮你讲清楚。

商品卖点讲解
这款商品的讲解重点建议围绕资料中已填写的核心卖点展开，用真实信息说明它为什么值得关注，不额外夸大未确认的效果。

用户痛点刺激
如果你遇到过资料中提到的使用痛点，可以重点听这一段。我们只基于当前商品信息做说明，不做绝对化承诺。

互动提问
大家可以在评论区打出你最关心的问题：价格、库存、适用人群、优惠，或者你自己的使用场景，我会按商品资料逐个回应。

优惠逼单
如果当前有优惠信息，建议主播明确说明优惠条件和下单入口；如果优惠信息不足，就提示以页面活动为准，避免制造不确定承诺。

异议回应
对是否适合自己有疑问的朋友，可以先对照适用人群和核心卖点。资料没有覆盖的情况，建议补充问题后再判断。

结尾转化
最后总结一下，这款商品适合对当前卖点有明确需求的用户。确认需要的朋友可以查看商品卡，下单前也可以继续留言确认关键信息。"""

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
        return """【AI模拟RAG回答】
根据已上传资料，当前问题可以从产品应用场景、客户需求匹配和下一步沟通三个方面分析。

1. 产品匹配：建议优先结合客户行业、屏幕尺寸、亮度、接口方式和交付周期进行判断。
2. 客户沟通：可以追问客户项目阶段、预计用量、应用场景和是否有定制需求。
3. 下一步动作：建议发送产品资料，并同步确认客户的技术参数要求和采购时间节点。

注意：当前为 mock 模式，如需真实回答，请在 .env 中配置 DeepSeek API。"""

    if "总结" in prompt:
        return """【AI模拟总结】
该客户已建立基础联系，目前需要重点判断真实采购需求、项目时间节点、预算情况和决策链条。
从现有跟进信息看，下一步不应只做普通寒暄，而应围绕客户业务场景继续追问需求，并沉淀关键信息。"""

    return """【AI模拟建议】
1. 先确认客户目前是否有明确项目、采购计划或替换需求。
2. 重点询问：应用场景、预计数量、预算范围、决策人、时间节点。
3. 可以准备一段简短话术：您好，我这边想根据贵司实际应用场景，帮您初步匹配更合适的方案，方便了解下目前项目大概处在哪个阶段吗？
4. 跟进后及时记录客户反馈，为后续报价或方案推荐做准备。"""
