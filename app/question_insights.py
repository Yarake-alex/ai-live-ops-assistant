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
