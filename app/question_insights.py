"""V3 商品问题记录与分类 helper。

- 纯关键词规则，不调用 LLM、不新增 NLP 依赖。
- record_product_question 为 best-effort：任何失败只记录 warning，
  绝不影响问答 / 评论助手主流程。
"""

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ProductQuestionLog

logger = logging.getLogger(__name__)

SOURCE_PRODUCT_ASK = "product_knowledge_ask"
SOURCE_COMMENT_REPLY = "comment_reply"

MAX_QUESTION_LEN = 500  # 与 ProductKnowledgeAsk / CommentReplyCreate 上限一致

# 关键词规则按优先级排列：risk 最高，避免「孕妇/儿童/过敏/不能用」等
# 高风险问题被误判为 audience 之类的低风险类别。
CATEGORY_KEYWORDS = [
    ("risk", ["孕妇", "儿童", "小孩", "过敏", "副作用", "禁忌", "不能用", "不适合", "刺激"]),
    ("after_sales", ["售后", "退换", "退货", "换货", "保修", "坏了"]),
    ("price", ["多少钱", "价格", "贵不贵", "几块", "多少米"]),
    ("stock", ["库存", "还有吗", "现货", "缺货"]),
    ("promotion", ["优惠", "活动", "券", "满减", "买一送一"]),
    ("audience", ["适合谁", "什么人用", "什么人", "敏感肌", "人群"]),
    ("selling_points", ["好在哪", "优势", "特点", "卖点"]),
    ("usage", ["怎么用", "用法", "步骤", "一天几次", "用量"]),
]


def normalize_question(text: str) -> str:
    """简单归一化：小写 + 去标点空白，不引入分词/NLP。"""
    if not text:
        return ""
    return re.sub(r"[\W_]+", "", text.lower().strip())[:MAX_QUESTION_LEN]


def classify_question(text: str) -> str:
    """按关键词规则分类；未命中返回 other。"""
    q = (text or "").lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(k in q for k in keywords):
            return category
    return "other"


# 本地快答仅支持低风险、确定性字段（V3 阶段 B）。
# risk / after_sales / usage / other 一律不快答，继续走商品资料检索。
LOCAL_ANSWER_CATEGORIES = ("price", "stock", "promotion", "audience", "selling_points")

# 分类 → 中文标签（问题洞察展示用）
CATEGORY_LABELS = {
    "price": "价格",
    "stock": "库存",
    "promotion": "优惠",
    "audience": "适用人群",
    "selling_points": "卖点",
    "usage": "使用方法",
    "after_sales": "售后",
    "risk": "风险边界",
    "other": "其他",
}


def _format_price(price) -> str:
    """把 Decimal 价格转成简洁字符串（129.00 → 129，129.50 → 129.5）。"""
    return str(float(price)).rstrip("0").rstrip(".")


def build_local_product_answer(product, category: str):
    """按商品字段构建本地快答；字段为空/不支持时返回 None。

    返回 {"answer": str, "category": str} 或 None。
    不调用 LLM、不走向量、不编造：答案只由商品字段模板生成。
    """
    if category not in LOCAL_ANSWER_CATEGORIES:
        return None

    if category == "price":
        if not product.price or product.price <= 0:
            return None
        return {
            "answer": f"这款商品当前价格是 ¥{_format_price(product.price)}，具体以直播间实际展示为准。",
            "category": "price",
        }

    if category == "stock":
        if not product.stock or product.stock <= 0:
            return None
        return {
            "answer": f"这款商品当前库存为 {product.stock} 件，库存会随下单变化，建议以实际下单页面为准。",
            "category": "stock",
        }

    if category == "promotion":
        if not (product.promotion or "").strip():
            return None
        return {
            "answer": f"当前优惠信息：{product.promotion}。具体活动规则以直播间说明为准。",
            "category": "promotion",
        }

    if category == "audience":
        if not (product.target_audience or "").strip():
            return None
        return {
            "answer": f"这款商品适合的人群：{product.target_audience}。如果有特殊情况，建议结合商品资料或咨询客服确认。",
            "category": "audience",
        }

    if category == "selling_points":
        if not (product.selling_points or "").strip():
            return None
        return {
            "answer": f"这款商品的核心卖点是：{product.selling_points}。",
            "category": "selling_points",
        }

    return None


def build_question_insights(db: Session, user_id: int, product_id: int):
    """统计当前用户 + 当前商品的问题日志（MVP：Python 聚合，不做复杂 SQL）。

    - top_questions：按 normalized_question 分组计数 Top 5，question/category 取组内最新一条
    - category_counts：9 类全量返回，无数据 count=0
    - recent_questions：最近 10 条（id 倒序）
    - unanswered_questions：was_answered=false 分组计数 Top 5
    """
    from app.schemas import (
        ProductQuestionInsightsOut,
        QuestionCategoryCount,
        QuestionTopItem,
        RecentQuestionItem,
    )

    logs = (
        db.query(ProductQuestionLog)
        .filter(
            ProductQuestionLog.user_id == user_id,
            ProductQuestionLog.product_id == product_id,
        )
        .order_by(ProductQuestionLog.id.desc())
        .all()
    )

    # 分组计数（logs 已按 id 倒序，组内第一次出现即最新一条）
    top_groups: dict = {}
    unanswered_groups: dict = {}
    category_counts = {cat: 0 for cat in CATEGORY_LABELS}

    for log in logs:
        key = log.normalized_question or log.question
        if log.category in category_counts:
            category_counts[log.category] += 1

        if key not in top_groups:
            top_groups[key] = {
                "question": log.question,
                "category": log.category,
                "count": 0,
            }
        top_groups[key]["count"] += 1

        if not log.was_answered:
            if key not in unanswered_groups:
                unanswered_groups[key] = {
                    "question": log.question,
                    "category": log.category,
                    "count": 0,
                }
            unanswered_groups[key]["count"] += 1

    top_questions = [
        QuestionTopItem(**item)
        for item in sorted(top_groups.values(), key=lambda x: -x["count"])[:5]
    ]
    unanswered_questions = [
        QuestionTopItem(**item)
        for item in sorted(unanswered_groups.values(), key=lambda x: -x["count"])[:5]
    ]

    return ProductQuestionInsightsOut(
        top_questions=top_questions,
        category_counts=[
            QuestionCategoryCount(category=cat, label=CATEGORY_LABELS[cat], count=n)
            for cat, n in category_counts.items()
        ],
        recent_questions=[
            RecentQuestionItem(
                question=log.question,
                category=log.category,
                answer_mode=log.answer_mode,
                was_answered=log.was_answered,
                created_at=log.created_at,
            )
            for log in logs[:10]
        ],
        unanswered_questions=unanswered_questions,
    )


def record_product_question(
    db: Session,
    *,
    user_id: int,
    product_id: int,
    source: str,
    question: str,
    category: Optional[str] = None,
    answer_mode: str = "llm",
    was_answered: bool = True,
) -> None:
    """写入一条商品问题记录（best-effort，失败不影响调用方）。

    只记录问题文本（截断到 500 字符），不记录回答内容。
    """
    try:
        raw = (question or "").strip()[:MAX_QUESTION_LEN]
        db.add(ProductQuestionLog(
            user_id=user_id,
            product_id=product_id,
            source=source,
            question=raw,
            normalized_question=normalize_question(raw),
            category=category or classify_question(raw),
            answer_mode=answer_mode,
            was_answered=was_answered,
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Failed to record product question (user=%s, product=%s): %s",
            user_id,
            product_id,
            exc,
        )
