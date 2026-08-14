from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerCreate(BaseModel):
    name: str
    company: str
    phone: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None
    level: Optional[str] = None
    intention: Optional[str] = None
    cooperation_status: Optional[str] = None
    source: Optional[str] = None
    remark: Optional[str] = None
    next_followup_at: Optional[datetime] = None
    followup_status: Optional[str] = "待跟进"


class CustomerOut(CustomerCreate):
    id: int
    last_followup_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowUpCreate(BaseModel):
    content: str
    next_action: Optional[str] = None
    next_followup_at: Optional[datetime] = None
    followup_status: Optional[str] = None


class FollowUpOut(FollowUpCreate):
    id: int
    customer_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


class AIResult(BaseModel):
    result: str


class RagAsk(BaseModel):
    question: str


class RagSource(BaseModel):
    filename: str
    chunk_index: int
    content: str


class RagAnswer(BaseModel):
    answer: str
    sources: List[RagSource]


class AgentAnalyzeRequest(BaseModel):
    customer_id: int
    task: Optional[str] = "帮我分析这个客户下一步怎么跟进"


class AgentAnalyzeResult(BaseModel):
    steps: List[str]
    result: str
    sources: List[RagSource]


class CustomerSearchResult(BaseModel):
    items: List[CustomerOut]
    total: int
    page: int
    page_size: int
    pages: int


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
