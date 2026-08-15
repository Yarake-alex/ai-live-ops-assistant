from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    products: Mapped[List["Product"]] = relationship(back_populates="owner")
    live_scripts: Mapped[List["LiveScript"]] = relationship(back_populates="owner")
    live_comment_replies: Mapped[List["LiveCommentReply"]] = relationship(back_populates="owner")
    product_knowledge_chunks: Mapped[List["ProductKnowledgeChunk"]] = relationship(back_populates="owner")
    live_reviews: Mapped[List["LiveReview"]] = relationship(back_populates="owner")
    document_chunks: Mapped[List["DocumentChunk"]] = relationship(back_populates="owner")


class Product(Base):
    """直播带货商品 — 直播运营核心业务主体。"""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    selling_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pain_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    promotion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    live_status: Mapped[str] = mapped_column(String(20), nullable=False, default="未上播")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    owner: Mapped["User"] = relationship(back_populates="products")
    live_scripts: Mapped[List["LiveScript"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    live_comment_replies: Mapped[List["LiveCommentReply"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    knowledge_chunks: Mapped[List["ProductKnowledgeChunk"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    live_reviews: Mapped[List["LiveReview"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )


class LiveScript(Base):
    """AI 直播话术生成记录。"""

    __tablename__ = "live_scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    owner: Mapped["User"] = relationship(back_populates="live_scripts")
    product: Mapped["Product"] = relationship(back_populates="live_scripts")


class LiveCommentReply(Base):
    """直播评论自动回复模拟记录。"""

    __tablename__ = "live_comment_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    reply: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    owner: Mapped["User"] = relationship(back_populates="live_comment_replies")
    product: Mapped["Product"] = relationship(back_populates="live_comment_replies")


class ProductKnowledgeChunk(Base):
    """商品知识库片段 — 独立于通用 RAG 的 DocumentChunk，按商品维度隔离。"""

    __tablename__ = "product_knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    owner: Mapped["User"] = relationship(back_populates="product_knowledge_chunks")
    product: Mapped["Product"] = relationship(back_populates="knowledge_chunks")


class LiveReview(Base):
    """直播复盘生成记录。"""

    __tablename__ = "live_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    owner: Mapped["User"] = relationship(back_populates="live_reviews")
    product: Mapped["Product"] = relationship(back_populates="live_reviews")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    owner: Mapped["User"] = relationship(back_populates="document_chunks")


class ProductQuestionLog(Base):
    """V3 商品问题记录 — 轻量日志，只记问题不记回答内容，按用户与商品隔离。"""

    __tablename__ = "product_question_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    # product_knowledge_ask | comment_reply
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_question: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    # price | stock | promotion | audience | selling_points | usage | after_sales | risk | other
    category: Mapped[str] = mapped_column(String(30), default="other", nullable=False, index=True)
    # product_knowledge | llm | fallback | no_match（local_rule 为后续阶段预留）
    answer_mode: Mapped[str] = mapped_column(String(30), default="llm", nullable=False)
    was_answered: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiCallLog(Base):
    """AI 调用日志 — 轻量用量记录，不保存 prompt 原文和 API Key。"""

    __tablename__ = "ai_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    feature: Mapped[str] = mapped_column(
        String(50), default="unknown", nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_response_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="success", nullable=False, index=True
    )  # success | fallback | error
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
