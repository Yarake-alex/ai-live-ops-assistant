from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── Product schemas ───


class ProductCreate(BaseModel):
    # 字段最大长度与数据库列定义对齐（products 表）
    name: str = Field(max_length=100)
    price: Decimal = Decimal("0")
    selling_points: Optional[str] = Field(default=None, max_length=2000)
    target_audience: Optional[str] = Field(default=None, max_length=2000)
    pain_points: Optional[str] = Field(default=None, max_length=2000)
    promotion: Optional[str] = Field(default=None, max_length=2000)
    stock: int = 0
    live_status: Optional[str] = Field(default="未上播", max_length=20)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("商品名称不能为空")
        return v

    @field_validator("price")
    @classmethod
    def price_must_not_be_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("价格不能为负数")
        return v

    @field_validator("stock")
    @classmethod
    def stock_must_not_be_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("库存不能为负数")
        return v


class ProductOut(ProductCreate):
    id: int
    # price 对外以数值输出（FastAPI 不会自动把 Decimal 转成 JSON 数字）
    price: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductSearchResult(BaseModel):
    items: List[ProductOut]
    total: int
    page: int
    page_size: int
    pages: int


class LiveScriptOut(BaseModel):
    id: int
    product_id: int
    content: str
    prompt: str
    provider: str
    model: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentReplyCreate(BaseModel):
    comment: str = Field(max_length=500)

    @field_validator("comment")
    @classmethod
    def comment_must_not_be_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("评论内容不能为空")
        return v


class LiveCommentReplyOut(BaseModel):
    id: int
    product_id: int
    comment: str
    reply: str
    prompt: str
    provider: str
    model: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Product knowledge base (商品知识库 RAG) ───


class ProductKnowledgeAsk(BaseModel):
    question: str = Field(max_length=500)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        return v


class ProductKnowledgeSource(BaseModel):
    filename: str
    chunk_index: int
    content: str


class ProductKnowledgeAnswer(BaseModel):
    answer: str
    sources: List[ProductKnowledgeSource]


class ProductKnowledgeDocument(BaseModel):
    filename: str
    chunks: int
    preview: Optional[str] = None
    updated_at: Optional[str] = None


# ─── Product readiness (商品资料完整度 + 开播准备) ───


class ProductCompleteness(BaseModel):
    """商品资料完整度评分（后端实时计算，不落库）。"""

    score: int
    missing_items: List[str]
    suggestions: List[str]


class PrepChecklistItem(BaseModel):
    """开播准备清单项（阶段 4 为最小占位结构，后续阶段填充）。"""

    key: str
    label: str
    status: str  # done | todo | recommended
    detail: str = ""


class ProductReadinessOut(BaseModel):
    completeness: ProductCompleteness
    prep_checklist: List[PrepChecklistItem]


# ─── Live review (直播复盘) ───


class LiveReviewOut(BaseModel):
    id: int
    product_id: int
    content: str
    prompt: str
    provider: str
    model: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Dashboard (轻量运营看板) ───


class DashboardStats(BaseModel):
    """旧版统计（兼容保留），新前端优先使用 LiveOpsDashboard。"""

    products: int
    live_products: int
    live_scripts: int
    comment_replies: int
    live_reviews: int
    knowledge_documents: int


class HotQuestion(BaseModel):
    comment: str
    count: int


class LiveOpsDashboard(BaseModel):
    """直播运营看板：当前用户的数据统计、高频评论与最近记录。"""

    product_count: int
    live_product_count: int
    live_script_count: int
    comment_reply_count: int
    live_review_count: int
    knowledge_document_count: int
    hot_questions: List[HotQuestion]
    recent_comment_replies: List[LiveCommentReplyOut]
    recent_live_reviews: List[LiveReviewOut]


class RagAsk(BaseModel):
    question: str


class RagSource(BaseModel):
    filename: str
    chunk_index: int
    content: str


class RagAnswer(BaseModel):
    answer: str
    sources: List[RagSource]


class RagDocument(BaseModel):
    filename: str
    chunks: int
    vector_indexed: Optional[int] = None  # number of indexed chunks, null when vector disabled
    updated_at: Optional[str] = None  # ISO string of the latest chunk's created_at
    preview: Optional[str] = None  # first ~120 chars of the first chunk


class RagChunkOut(BaseModel):
    chunk_index: int
    content: str
    created_at: str


class RagChunkList(BaseModel):
    filename: str
    chunks: List[RagChunkOut]


# ─── Auth / User schemas ───


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"


class UserStatusUpdate(BaseModel):
    is_active: bool


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
