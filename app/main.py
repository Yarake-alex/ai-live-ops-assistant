import csv
import io
import hmac
import json
import base64
import logging
from collections import Counter
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError

from app.database import get_db
from app.config import settings
from app.models import (
    Product,
    LiveScript,
    LiveCommentReply,
    ProductKnowledgeChunk,
    LiveReview,
    DocumentChunk,
    User,
)
from app.auth import create_user, verify_password, hash_password, utc_timestamp
from app.schemas import (
    ProductCreate,
    ProductOut,
    ProductSearchResult,
    LiveScriptOut,
    CommentReplyCreate,
    LiveCommentReplyOut,
    ProductKnowledgeAsk,
    ProductKnowledgeAnswer,
    ProductKnowledgeSource,
    ProductKnowledgeDocument,
    LiveReviewOut,
    DashboardStats,
    HotQuestion,
    LiveOpsDashboard,
    RagAsk,
    RagAnswer,
    RagSource,
    RagDocument,
    RagChunkOut,
    RagChunkList,
    ProductCompleteness,
    PrepChecklistItem,
    ProductReadinessOut,
    ProductQuestionInsightsOut,
    ProductOpsSuggestionsOut,
    UserOut,
    UserCreateRequest,
    UserStatusUpdate,
    ChangePasswordRequest,
)
from app.llm import (
    FALLBACK_MESSAGE,
    build_live_comment_reply_fallback,
    build_live_comment_reply_prompt,
    build_live_review_fallback,
    build_live_review_prompt,
    build_live_script_fallback,
    build_live_script_prompt,
    build_product_rag_prompt,
    call_llm,
    resolve_llm_provider_model,
)
from app.rag import (
    extract_text_from_upload,
    split_text,
    retrieve_chunks_vector,
    retrieve_product_chunks_vector,
    build_rag_prompt,
)
from app.db_init import init_database
from app.question_insights import (
    record_product_question,
    classify_question,
    build_local_product_answer,
    build_question_insights,
    build_ops_suggestions,
    build_script_context_from_questions,
    SOURCE_PRODUCT_ASK,
    SOURCE_COMMENT_REPLY,
)

logger = logging.getLogger(__name__)

# ─── Production security validation — MUST run BEFORE init_database() ───
# In production, invalid config must block startup before touching the database.
if settings.APP_ENV == "production":
    from app.config import validate_production_settings
    try:
        _prod_warnings = validate_production_settings()
        for _w in _prod_warnings:
            logger.warning("Production config: %s", _w)
    except ValueError as exc:
        logger.critical("Production config fatal: %s", exc)
        raise

init_database()

app = FastAPI(
    title="AI 直播运营助手 MVP",
    description="商品知识库 RAG + 直播复盘 + 轻量运营看板",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Security headers middleware (lightweight, no new deps) ───
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    from fastapi.responses import Response as _Response
    response: _Response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Session token helpers (stdlib HMAC, no extra deps) ───

def _make_user_session_token(user_id: int, secret: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"uid": user_id, "t": utc_timestamp()}).encode()
    ).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), payload.encode(), "sha256").digest()
    ).rstrip(b"=").decode()
    return f"{payload}.{sig}"


def _verify_session_token(token: str, secret: str) -> Optional[dict]:
    if "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    expected_sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), payload.encode(), "sha256").digest()
    ).rstrip(b"=").decode()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(payload + "=="))
    except Exception:
        return None


# ─── Auth dependency ───

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """返回当前用户；APP_ACCESS_PASSWORD 为空时使用本地开发默认用户。"""
    if not settings.APP_ACCESS_PASSWORD:
        user = db.query(User).filter(User.username == settings.APP_ADMIN_USERNAME).first()
        if not user:
            raise HTTPException(status_code=500, detail="本地开发用户初始化失败")
        return user

    token = request.cookies.get("session")
    payload = _verify_session_token(token, settings.SESSION_SECRET) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    user_id = payload.get("uid")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户为管理员（role == 'admin'），否则返回 403。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return current_user


# ─── Auth routes (no login required) ───

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: str


@app.post("/auth/login")
def auth_login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    if not settings.APP_ACCESS_PASSWORD:
        return {"message": "登录成功（本地开发模式）"}

    username = (data.username or settings.APP_ADMIN_USERNAME).strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    token = _make_user_session_token(user.id, settings.SESSION_SECRET)
    resp = JSONResponse({"message": "登录成功", "username": user.username})
    resp.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=86400 * 7,
    )
    return resp


@app.post("/auth/users", response_model=UserOut)
def create_app_user(
    data: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    username = data.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少 3 个字符")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 个字符")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")

    role = data.role.strip() if data.role else "user"
    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role 只能是 admin 或 user")

    user = create_user(
        db=db,
        username=username,
        password=data.password,
        is_admin=(role == "admin"),
        role=role,
    )
    return user


@app.post("/auth/register")
def register_user(data: UserCreateRequest, db: Session = Depends(get_db)):
    if not settings.ENABLE_PUBLIC_REGISTRATION:
        raise HTTPException(status_code=403, detail="当前未开放公开注册")

    username = data.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少 3 个字符")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 个字符")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = create_user(db=db, username=username, password=data.password, is_admin=False)
    return {"id": user.id, "username": user.username, "is_admin": user.is_admin}


@app.post("/auth/logout")
def auth_logout():
    resp = JSONResponse({"message": "已退出登录"})
    resp.delete_cookie(key="session", path="/")
    return resp


@app.get("/auth/me")
def auth_me(request: Request, db: Session = Depends(get_db)):
    if not settings.APP_ACCESS_PASSWORD:
        return {"logged_in": True, "username": settings.APP_ADMIN_USERNAME, "role": "admin", "is_active": True}
    token = request.cookies.get("session")
    payload = _verify_session_token(token, settings.SESSION_SECRET) if token else None
    if payload:
        user = db.query(User).filter(User.id == payload.get("uid")).first()
        if user:
            return {
                "logged_in": True,
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
            }
    return {"logged_in": False}


@app.get("/auth/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员查看用户列表。"""
    return db.query(User).order_by(User.id.asc()).all()


@app.patch("/auth/users/{user_id}/status")
def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员启用/禁用用户。不能禁用自己。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用当前登录的管理员账号")
    user.is_active = data.is_active
    db.commit()
    return {"id": user.id, "username": user.username, "is_active": user.is_active}


@app.post("/auth/change-password")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """当前用户修改自己的密码。"""
    if not data.old_password:
        raise HTTPException(status_code=400, detail="旧密码不能为空")
    if not data.new_password or len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 个字符")

    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")

    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "密码修改成功"}


# ─── Public routes ───

@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/health")
def health_check():
    """部署健康检查接口，不需要登录。"""
    return {"status": "ok"}


# ─── Business routes (all require login) ───



# ─── Product routes (live ops — 商品管理) ───

# 商品 CSV 导入限制
MAX_PRODUCT_CSV_BYTES = 5 * 1024 * 1024  # 5MB
MAX_PRODUCT_CSV_ROWS = 5000

# CSV 中文表头 → 英文字段名映射。导入同时兼容中文和英文表头。
_PRODUCT_CSV_HEADER_ALIASES = {
    "商品名称": "name",
    "价格": "price",
    "核心卖点": "selling_points",
    "适用人群": "target_audience",
    "用户痛点": "pain_points",
    "优惠信息": "promotion",
    "库存": "stock",
    "直播状态": "live_status",
    "备注": "notes",
}


def get_product_for_user(db: Session, product_id: int, user: User) -> Product:
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.user_id == user.id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product


def get_live_script_for_user(db: Session, script_id: int, user: User) -> LiveScript:
    script = (
        db.query(LiveScript)
        .filter(LiveScript.id == script_id, LiveScript.user_id == user.id)
        .first()
    )
    if not script:
        raise HTTPException(status_code=404, detail="直播话术不存在")
    return script


def get_comment_reply_for_user(db: Session, reply_id: int, user: User) -> LiveCommentReply:
    reply = (
        db.query(LiveCommentReply)
        .filter(LiveCommentReply.id == reply_id, LiveCommentReply.user_id == user.id)
        .first()
    )
    if not reply:
        raise HTTPException(status_code=404, detail="评论回复记录不存在")
    return reply


def _format_validation_error(exc: ValidationError) -> str:
    """把 Pydantic 校验错误格式化为可读的行级原因，例如「price: Input should be a valid decimal」。"""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        msg = err.get("msg", "字段格式不正确")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts)


@app.post("/products", response_model=ProductOut)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product_data = data.model_dump()
    if not product_data.get("live_status"):
        product_data["live_status"] = "未上播"
    product = Product(user_id=current_user.id, **product_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.get("/products", response_model=List[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Product)
        .filter(Product.user_id == current_user.id)
        .order_by(Product.id.desc())
        .all()
    )


@app.get("/products/search", response_model=ProductSearchResult)
def search_products(
    q: Optional[str] = None,
    live_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜索/筛选/分页 查询当前用户商品。"""
    query = db.query(Product).filter(Product.user_id == current_user.id)

    # 关键词搜索：名称、核心卖点、适用人群、用户痛点、优惠信息、备注
    if q:
        q_like = f"%{q}%"
        query = query.filter(or_(
            Product.name.ilike(q_like),
            Product.selling_points.ilike(q_like),
            Product.target_audience.ilike(q_like),
            Product.pain_points.ilike(q_like),
            Product.promotion.ilike(q_like),
            Product.notes.ilike(q_like),
        ))

    # 精确筛选
    if live_status:
        query = query.filter(Product.live_status == live_status)

    # 总数
    total = query.count()

    # 分页参数修正
    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)

    # 排序
    query = query.order_by(Product.id.desc())

    # 总页数
    pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 0
    if page > pages and total > 0:
        page = pages

    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    return ProductSearchResult(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@app.post("/products/import")
def import_products_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入商品 CSV 文件，只导入到当前用户。

    表头支持英文（name/price/selling_points/target_audience/pain_points/
    promotion/stock/live_status/notes）或中文（商品名称/价格/核心卖点/
    适用人群/用户痛点/优惠信息/库存/直播状态/备注）。
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传 CSV 文件")

    try:
        # 有界读取：最多多读 1 字节用于判定超限，避免把超大文件整体读入内存
        raw = file.file.read(MAX_PRODUCT_CSV_BYTES + 1)
    except Exception:
        raise HTTPException(status_code=400, detail="无法读取文件内容")

    if len(raw) > MAX_PRODUCT_CSV_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"CSV 文件过大，最大支持 {MAX_PRODUCT_CSV_BYTES // (1024 * 1024)}MB",
        )

    # 尝试 UTF-8-SIG 和 UTF-8 解码
    content = None
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            content = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise HTTPException(status_code=400, detail="文件编码不支持，请使用 UTF-8 编码的 CSV 文件")

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV 文件没有任何列")

    # 行数上限检查：先整体计数（csv 解析器可正确处理带引号的换行），超限直接拒绝
    row_count = sum(1 for _ in reader)
    if row_count > MAX_PRODUCT_CSV_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"CSV 行数过多，最多支持 {MAX_PRODUCT_CSV_ROWS} 行",
        )

    # 重新解析用于逐行处理
    reader = csv.DictReader(io.StringIO(content))

    created = 0
    skipped = 0
    errors: list[dict] = []

    # 批量内去重追踪（导入过程中尚未提交到数据库的记录），按商品名称去重
    batch_seen: set[str] = set()

    for row_num, row in enumerate(reader, start=2):
        # 中文表头 → 英文字段名
        row = {_PRODUCT_CSV_HEADER_ALIASES.get(k, k): v for k, v in row.items()}
        try:
            # 复用 ProductCreate schema 校验，与 JSON API 规则保持一致：
            # name trim 非空且 <=100、price >=0、stock >=0 整数、
            # live_status <=20、长文本字段 <=2000
            product_data = ProductCreate(
                name=(row.get("name") or "").strip(),
                price=(row.get("price") or "").strip() or "0",
                selling_points=(row.get("selling_points") or "").strip() or None,
                target_audience=(row.get("target_audience") or "").strip() or None,
                pain_points=(row.get("pain_points") or "").strip() or None,
                promotion=(row.get("promotion") or "").strip() or None,
                stock=(row.get("stock") or "").strip() or "0",
                live_status=(row.get("live_status") or "").strip() or "未上播",
                notes=(row.get("notes") or "").strip() or None,
            )
            name = product_data.name

            # 重复检测：当前用户名下同名商品视为重复
            existing_in_db = (
                db.query(Product)
                .filter(
                    Product.user_id == current_user.id,
                    Product.name == name,
                )
                .first()
            )
            if existing_in_db or name in batch_seen:
                skipped += 1
                continue

            # 只有通过所有校验、确定要创建的行才加入去重集合
            batch_seen.add(name)

            product = Product(user_id=current_user.id, **product_data.model_dump())
            db.add(product)
            created += 1
        except ValidationError as exc:
            # 可预期的 Pydantic 校验错误——按行返回清晰原因（ValidationError 是 ValueError 子类，须先捕获）
            errors.append({"row": row_num, "reason": _format_validation_error(exc)})
        except ValueError as exc:
            # 其他可预期错误——返回清晰原因
            errors.append({"row": row_num, "reason": str(exc)})
        except Exception:
            # 未知异常——只返回通用行级错误，内部细节记录到日志
            logger.exception(
                "Product CSV import row %d failed (user=%s)",
                row_num,
                current_user.id,
            )
            errors.append({"row": row_num, "reason": "该行数据格式不正确"})

    db.commit()

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


@app.get("/products/export")
def export_products_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出当前用户商品为 CSV 文件（UTF-8-SIG，英文表头）。"""
    products = (
        db.query(Product)
        .filter(Product.user_id == current_user.id)
        .order_by(Product.id.asc())
        .all()
    )

    output = io.StringIO()
    output.write("﻿")  # UTF-8 BOM

    fieldnames = [
        "name", "price", "selling_points", "target_audience", "pain_points",
        "promotion", "stock", "live_status", "notes", "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for p in products:
        writer.writerow({
            "name": p.name,
            "price": str(p.price),
            "selling_points": p.selling_points or "",
            "target_audience": p.target_audience or "",
            "pain_points": p.pain_points or "",
            "promotion": p.promotion or "",
            "stock": p.stock,
            "live_status": p.live_status or "",
            "notes": p.notes or "",
            "created_at": p.created_at.isoformat() if p.created_at else "",
        })

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": "attachment; filename=products_export.csv",
        },
    )


@app.post("/products/{product_id}/live-scripts", response_model=LiveScriptOut)
def generate_live_script(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = get_product_for_user(db, product_id, current_user)
    # V4 阶段 5：话术上下文来自当前用户+商品的问题洞察（best-effort，失败不影响生成）
    try:
        script_context = build_script_context_from_questions(db, current_user.id, product.id)
    except Exception as exc:
        logger.warning("Script context unavailable for product %s: %s", product.id, exc)
        script_context = None
    prompt = build_live_script_prompt(product, script_context=script_context)
    provider, model = resolve_llm_provider_model()
    status = "success"
    error_message = None
    content = ""

    try:
        content = call_llm(
            prompt,
            feature="live_script_generation",
            user_id=current_user.id,
            db=db,
        )
    except Exception:
        # call_llm 内部已兜底，正常情况下不会抛异常；保险起见统一走兜底路径
        logger.exception(
            "Live script AI call raised unexpectedly (user=%s, product=%s)",
            current_user.id,
            product_id,
        )
        content = ""

    if content and FALLBACK_MESSAGE not in content:
        status = "success"
    else:
        # AI 不可用 → 尝试本地兜底话术（同样带上问题洞察上下文）
        try:
            content = build_live_script_fallback(product, script_context=script_context)
            status = "fallback"
            error_message = "AI 服务暂时不可用，已返回本地兜底话术"
        except Exception:
            # 兜底也失败 → 记录 failed 状态（可追踪），细节只进日志
            logger.exception(
                "Live script fallback generation failed (user=%s, product=%s)",
                current_user.id,
                product_id,
            )
            content = ""
            status = "failed"
            error_message = "AI 服务暂时不可用，且本地兜底话术生成失败，请稍后重试"

    script = LiveScript(
        user_id=current_user.id,
        product_id=product.id,
        content=content,
        prompt=prompt,
        provider=provider,
        model=model,
        status=status,
        error_message=error_message,
    )
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


@app.get("/products/{product_id}/live-scripts", response_model=List[LiveScriptOut])
def list_product_live_scripts(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = get_product_for_user(db, product_id, current_user)
    return (
        db.query(LiveScript)
        .filter(
            LiveScript.product_id == product.id,
            LiveScript.user_id == current_user.id,
        )
        .order_by(LiveScript.created_at.desc(), LiveScript.id.desc())
        .all()
    )


@app.get("/live-scripts/{script_id}", response_model=LiveScriptOut)
def get_live_script(
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_live_script_for_user(db, script_id, current_user)


# ─── Live comment reply routes (直播评论自动回复模拟) ───


@app.post("/products/{product_id}/comment-replies", response_model=LiveCommentReplyOut)
def generate_comment_reply(
    product_id: int,
    data: CommentReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于商品资料为一条模拟评论生成主播口吻回复。"""
    product = get_product_for_user(db, product_id, current_user)
    comment = data.comment
    prompt = build_live_comment_reply_prompt(product, comment)
    provider, model = resolve_llm_provider_model()
    status = "success"
    error_message = None
    reply = ""

    try:
        reply = call_llm(
            prompt,
            feature="live_comment_reply",
            user_id=current_user.id,
            db=db,
        )
    except Exception:
        # call_llm 内部已兜底，正常情况下不会抛异常；保险起见统一走兜底路径
        logger.exception(
            "Comment reply AI call raised unexpectedly (user=%s, product=%s)",
            current_user.id,
            product_id,
        )
        reply = ""

    if reply and FALLBACK_MESSAGE not in reply:
        status = "success"
    else:
        # AI 不可用 → 尝试本地兜底回复
        try:
            reply = build_live_comment_reply_fallback(product, comment)
            status = "fallback"
            error_message = "AI 服务暂时不可用，已返回本地兜底回复"
        except Exception:
            # 兜底也失败 → 记录 failed 状态（可追踪），细节只进日志
            logger.exception(
                "Comment reply fallback generation failed (user=%s, product=%s)",
                current_user.id,
                product_id,
            )
            reply = ""
            status = "failed"
            error_message = "AI 服务暂时不可用，且本地兜底回复生成失败，请稍后重试"

    record = LiveCommentReply(
        user_id=current_user.id,
        product_id=product.id,
        comment=comment,
        reply=reply,
        prompt=prompt,
        provider=provider,
        model=model,
        status=status,
        error_message=error_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # V3 问题记录：只记输入评论与结果模式，不改变生成逻辑
    record_product_question(
        db,
        user_id=current_user.id,
        product_id=product.id,
        source=SOURCE_COMMENT_REPLY,
        question=comment,
        answer_mode={"success": "llm", "fallback": "fallback", "failed": "no_match"}.get(
            status, "fallback"
        ),
        was_answered=(status != "failed"),
    )
    return record


@app.get("/products/{product_id}/comment-replies", response_model=List[LiveCommentReplyOut])
def list_product_comment_replies(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = get_product_for_user(db, product_id, current_user)
    return (
        db.query(LiveCommentReply)
        .filter(
            LiveCommentReply.product_id == product.id,
            LiveCommentReply.user_id == current_user.id,
        )
        .order_by(LiveCommentReply.created_at.desc(), LiveCommentReply.id.desc())
        .all()
    )


@app.get("/comment-replies/{reply_id}", response_model=LiveCommentReplyOut)
def get_comment_reply(
    reply_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_comment_reply_for_user(db, reply_id, current_user)


# ─── Product knowledge base routes (商品知识库 RAG) ───


@app.post("/products/{product_id}/knowledge/upload")
async def upload_product_knowledge(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传商品知识库文档（PDF/TXT/MD/CSV），片段按商品隔离存储。"""
    product = get_product_for_user(db, product_id, current_user)

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    parts = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail=f"文件过大，最大允许 {settings.MAX_UPLOAD_SIZE_MB}MB")
        parts.append(chunk)
    data = b"".join(parts)

    text_content = extract_text_from_upload(file, data)
    chunks = split_text(text_content)
    if not chunks:
        raise HTTPException(status_code=400, detail="文件内容为空，无法加入知识库")

    filename = file.filename or "unnamed"
    # 同名文件重新上传时，先清理该商品下该文件的旧向量索引，再删除旧 SQL 片段，
    # 避免旧索引残留（只影响当前用户、当前商品，不影响其他同名文件）
    if settings.VECTOR_SEARCH_ENABLED:
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store()
            if vs is not None and getattr(vs, "supports_product_knowledge", False):
                vs.delete_product_file_chunks(current_user.id, product.id, filename)
        except Exception as exc:
            logger.warning(f"Product vector pre-cleanup failed for '{filename}': {exc}")

    db.query(ProductKnowledgeChunk).filter(
        ProductKnowledgeChunk.filename == filename,
        ProductKnowledgeChunk.product_id == product.id,
        ProductKnowledgeChunk.user_id == current_user.id,
    ).delete()

    for index, chunk in enumerate(chunks, start=1):
        db.add(ProductKnowledgeChunk(
            user_id=current_user.id,
            product_id=product.id,
            filename=filename,
            chunk_index=index,
            content=chunk,
        ))

    db.commit()

    # ── 商品资料向量索引（fire-and-forget — 失败不影响上传成功） ──
    if settings.VECTOR_SEARCH_ENABLED:
        try:
            from app.embeddings import get_embedding_service
            from app.vector_store import get_vector_store

            emb_svc = get_embedding_service()
            vs = get_vector_store()
            if vs is not None and getattr(vs, "supports_product_knowledge", False):
                new_chunks = (
                    db.query(ProductKnowledgeChunk)
                    .filter(
                        ProductKnowledgeChunk.filename == filename,
                        ProductKnowledgeChunk.product_id == product.id,
                        ProductKnowledgeChunk.user_id == current_user.id,
                    )
                    .order_by(ProductKnowledgeChunk.id.asc())
                    .all()
                )
                if new_chunks:
                    texts = [c.content for c in new_chunks]
                    embeddings = emb_svc.embed_documents(texts)
                    vs.add_product_chunks(
                        ids=[c.id for c in new_chunks],
                        embeddings=embeddings,
                        metadatas=[
                            {
                                "user_id": c.user_id,
                                "product_id": c.product_id,
                                "filename": c.filename,
                                "chunk_index": c.chunk_index,
                                "source_type": "product_knowledge",
                            }
                            for c in new_chunks
                        ],
                    )
                    logger.info(
                        f"Product vector indexed {len(new_chunks)} chunks "
                        f"for file '{filename}' (product={product.id})"
                    )
        except Exception as exc:
            logger.warning(f"Product vector indexing skipped (upload continues): {exc}")

    return {"filename": filename, "chunks": len(chunks)}


@app.get("/products/{product_id}/knowledge/documents", response_model=List[ProductKnowledgeDocument])
def list_product_knowledge_documents(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = get_product_for_user(db, product_id, current_user)
    chunks = (
        db.query(ProductKnowledgeChunk)
        .filter(
            ProductKnowledgeChunk.product_id == product.id,
            ProductKnowledgeChunk.user_id == current_user.id,
        )
        .order_by(ProductKnowledgeChunk.filename.asc(), ProductKnowledgeChunk.chunk_index.asc())
        .all()
    )

    grouped: dict[str, list] = {}
    for c in chunks:
        grouped.setdefault(c.filename, []).append(c)

    return [
        ProductKnowledgeDocument(
            filename=fn,
            chunks=len(doc_chunks),
            preview=(doc_chunks[0].content[:120] if doc_chunks else None),
            updated_at=(max(c.created_at for c in doc_chunks).isoformat() if doc_chunks else None),
        )
        for fn, doc_chunks in grouped.items()
    ]


@app.delete("/products/{product_id}/knowledge/documents/{filename}")
def delete_product_knowledge_document(
    product_id: int,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = get_product_for_user(db, product_id, current_user)
    deleted = (
        db.query(ProductKnowledgeChunk)
        .filter(
            ProductKnowledgeChunk.product_id == product.id,
            ProductKnowledgeChunk.user_id == current_user.id,
            ProductKnowledgeChunk.filename == filename,
        )
        .delete()
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在")

    # ── 同步清理该用户、该商品、该文件的商品资料向量索引（失败不阻止删除） ──
    vector_warning: Optional[str] = None
    if settings.VECTOR_SEARCH_ENABLED:
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store()
            if vs is not None and getattr(vs, "supports_product_knowledge", False):
                vs.delete_product_file_chunks(current_user.id, product.id, filename)
            elif vs is None:
                vector_warning = "资料索引清理失败（索引服务不可用），可稍后点击「重建资料索引」"
        except Exception as exc:
            logger.error(f"Product vector cleanup failed for file '{filename}': {exc}")
            vector_warning = "资料索引清理失败，可稍后点击「重建资料索引」"

    resp = {"message": "文档已删除"}
    if vector_warning:
        resp["vector_warning"] = vector_warning
    return resp


@app.get("/products/{product_id}/knowledge/documents/{filename}/chunks", response_model=RagChunkList)
def list_product_knowledge_chunks(
    product_id: int,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查看商品知识库单个文件的全部片段（对应「查看片段」按钮）。"""
    product = get_product_for_user(db, product_id, current_user)
    chunks = (
        db.query(ProductKnowledgeChunk)
        .filter(
            ProductKnowledgeChunk.product_id == product.id,
            ProductKnowledgeChunk.user_id == current_user.id,
            ProductKnowledgeChunk.filename == filename,
        )
        .order_by(ProductKnowledgeChunk.chunk_index.asc())
        .all()
    )
    if not chunks:
        raise HTTPException(status_code=404, detail="资料文件不存在")

    return RagChunkList(
        filename=filename,
        chunks=[
            RagChunkOut(
                chunk_index=c.chunk_index,
                content=c.content,
                created_at=c.created_at.isoformat() if c.created_at else "",
            )
            for c in chunks
        ],
    )


@app.post("/products/{product_id}/knowledge/documents/{filename}/reindex")
def reindex_product_knowledge_file(
    product_id: int,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新整理该文件的资料检索索引（向量启用时真实重建；未启用时返回提示）。"""
    product = get_product_for_user(db, product_id, current_user)
    chunks = (
        db.query(ProductKnowledgeChunk)
        .filter(
            ProductKnowledgeChunk.product_id == product.id,
            ProductKnowledgeChunk.user_id == current_user.id,
            ProductKnowledgeChunk.filename == filename,
        )
        .order_by(ProductKnowledgeChunk.id.asc())
        .all()
    )
    if not chunks:
        raise HTTPException(status_code=404, detail="资料文件不存在")

    if not settings.VECTOR_SEARCH_ENABLED:
        return {
            "reindexed": False,
            "message": "资料索引功能未启用",
            "filename": filename,
            "chunks": len(chunks),
        }

    try:
        from app.embeddings import get_embedding_service
        from app.vector_store import get_vector_store

        emb_svc = get_embedding_service()
        vs = get_vector_store()
        if vs is None:
            raise RuntimeError("Vector store unavailable")
        if not getattr(vs, "supports_product_knowledge", False):
            # 向量存储存在但不支持商品资料索引（如 pgvector 场景）→ 视为未启用
            return {
                "reindexed": False,
                "message": "资料索引功能未启用",
                "filename": filename,
                "chunks": len(chunks),
            }
    except Exception as exc:
        # 索引服务暂不可用不是错误——返回未重建，前端继续使用基础资料检索
        logger.warning("Product reindex init failed for file '%s': %s", filename, exc)
        return {
            "reindexed": False,
            "message": "资料索引服务暂不可用，可继续使用基础资料检索",
            "filename": filename,
            "chunks": len(chunks),
        }

    try:
        # 先清理该用户、该商品、该文件的旧索引，再重新写入
        vs.delete_product_file_chunks(current_user.id, product.id, filename)

        texts = [c.content for c in chunks]
        embeddings = emb_svc.embed_documents(texts)
        vs.add_product_chunks(
            ids=[c.id for c in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "user_id": c.user_id,
                    "product_id": c.product_id,
                    "filename": c.filename,
                    "chunk_index": c.chunk_index,
                    "source_type": "product_knowledge",
                }
                for c in chunks
            ],
        )

        logger.info(
            "Reindexed %d product chunks for file '%s', product %d, user %d",
            len(chunks), filename, product.id, current_user.id,
        )
        return {
            "message": f"文件 {filename} 重新整理完成，共处理 {len(chunks)} 个片段",
            "chunks": len(chunks),
            "reindexed": True,
            "filename": filename,
        }
    except Exception as exc:
        # embedding 调用失败 / 网络异常等：不向用户暴露底层异常，
        # 返回未重建提示，问答继续走基础资料检索
        logger.warning("Product reindex failed for file '%s': %s", filename, exc)
        return {
            "reindexed": False,
            "message": "资料索引服务暂不可用，可继续使用基础资料检索",
            "filename": filename,
            "chunks": len(chunks),
        }


@app.post("/products/{product_id}/knowledge/ask", response_model=ProductKnowledgeAnswer)
def ask_product_knowledge(
    product_id: int,
    data: ProductKnowledgeAsk,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于商品资料文档回答问题（低风险本地快答 → 商品资料向量检索 → 自动降级 TF-IDF）。"""
    product = get_product_for_user(db, product_id, current_user)

    # ── V3 本地快答：低风险确定性字段直接回答，不调 LLM、不走向量 ──
    question_category = classify_question(data.question)
    local_answer = build_local_product_answer(product, question_category)
    if local_answer:
        record_product_question(
            db,
            user_id=current_user.id,
            product_id=product.id,
            source=SOURCE_PRODUCT_ASK,
            question=data.question,
            category=local_answer["category"],
            answer_mode="local_rule",
            was_answered=True,
        )
        return ProductKnowledgeAnswer(answer=local_answer["answer"], sources=[])

    chunks = (
        db.query(ProductKnowledgeChunk)
        .filter(
            ProductKnowledgeChunk.product_id == product.id,
            ProductKnowledgeChunk.user_id == current_user.id,
        )
        .order_by(ProductKnowledgeChunk.id.asc())
        .all()
    )
    if not chunks:
        record_product_question(
            db,
            user_id=current_user.id,
            product_id=product.id,
            source=SOURCE_PRODUCT_ASK,
            question=data.question,
            answer_mode="no_match",
            was_answered=False,
        )
        return ProductKnowledgeAnswer(
            answer="该商品还没有知识库资料，请先在商品详情页上传资料。",
            sources=[],
        )

    top = retrieve_product_chunks_vector(
        db,
        data.question,
        current_user.id,
        product.id,
        chunks,
        top_k=4,
    )
    if not top:
        record_product_question(
            db,
            user_id=current_user.id,
            product_id=product.id,
            source=SOURCE_PRODUCT_ASK,
            question=data.question,
            answer_mode="no_match",
            was_answered=False,
        )
        return ProductKnowledgeAnswer(
            answer="没有检索到与问题相关的商品资料，建议补充相关资料或换个问法。",
            sources=[],
        )

    prompt = build_product_rag_prompt(product, data.question, top)
    answer = call_llm(
        prompt,
        feature="product_rag_ask",
        user_id=current_user.id,
        db=db,
    )
    is_fallback = not answer or FALLBACK_MESSAGE in answer
    if is_fallback:
        answer = "AI 服务暂时不可用，请稍后重试；可先查看资料列表确认已上传内容。"

    sources = [
        ProductKnowledgeSource(
            filename=c.filename,
            chunk_index=c.chunk_index,
            content=c.content[:200],
        )
        for c in top
    ]
    # V3 问题记录：fallback 也计为已应答（用户拿到了可用提示），分类仍用于洞察
    record_product_question(
        db,
        user_id=current_user.id,
        product_id=product.id,
        source=SOURCE_PRODUCT_ASK,
        question=data.question,
        answer_mode="fallback" if is_fallback else "product_knowledge",
        was_answered=True,
    )
    return ProductKnowledgeAnswer(answer=answer, sources=sources)


# ─── Product readiness (商品资料完整度评分，实时计算) ───


# 评分维度：12 项，逐项命中计分。文件名关键词匹配大小写不敏感。
_COMPLETENESS_DIMENSIONS = [
    ("商品名称", lambda p, filenames, has_chunks: bool((p.name or "").strip())),
    ("价格", lambda p, filenames, has_chunks: (p.price or 0) > 0),
    ("库存", lambda p, filenames, has_chunks: (p.stock or 0) > 0),
    ("直播状态", lambda p, filenames, has_chunks: bool((p.live_status or "").strip())),
    ("核心卖点", lambda p, filenames, has_chunks: bool((p.selling_points or "").strip())),
    ("适用人群", lambda p, filenames, has_chunks: bool((p.target_audience or "").strip())),
    ("用户痛点", lambda p, filenames, has_chunks: bool((p.pain_points or "").strip())),
    ("优惠信息", lambda p, filenames, has_chunks: bool((p.promotion or "").strip())),
    ("商品资料文档", lambda p, filenames, has_chunks: has_chunks),
    (
        "FAQ 或问答资料",
        lambda p, filenames, has_chunks: any(
            any(k in fn.lower() for k in ("faq", "问答", "q&a")) for fn in filenames
        ),
    ),
    (
        "售后规则",
        lambda p, filenames, has_chunks: any(
            any(k in fn.lower() for k in ("售后", "退换", "after")) for fn in filenames
        ),
    ),
    (
        "风险边界",
        lambda p, filenames, has_chunks: bool((p.notes or "").strip())
        or any(
            any(k in fn.lower() for k in ("风险", "边界", "禁用", "不可承诺", "合规"))
            for fn in filenames
        ),
    ),
]

# 缺失项 → 固定建议文案（确定性映射，不调用 LLM）
_COMPLETENESS_SUGGESTIONS = {
    "商品名称": "补充商品名称",
    "价格": "填写商品价格",
    "库存": "填写库存数量",
    "直播状态": "设置直播状态",
    "核心卖点": "补充核心卖点",
    "适用人群": "补充适用人群",
    "用户痛点": "补充用户痛点",
    "优惠信息": "补充优惠信息",
    "商品资料文档": "上传商品资料文档",
    "FAQ 或问答资料": "建议上传 FAQ 或问答资料",
    "售后规则": "建议补充售后规则文档",
    "风险边界": "建议补充禁用话术或不可承诺内容",
}


def _compute_product_completeness(
    product: Product, filenames: List[str], has_chunks: bool
) -> ProductCompleteness:
    """按确定性规则实时计算商品资料完整度（不落库、不调用 LLM）。"""
    missing: List[str] = []
    hit = 0
    for label, check in _COMPLETENESS_DIMENSIONS:
        if check(product, filenames, has_chunks):
            hit += 1
        else:
            missing.append(label)

    total = len(_COMPLETENESS_DIMENSIONS)
    return ProductCompleteness(
        score=int(hit * 100 / total),
        missing_items=missing,
        suggestions=[_COMPLETENESS_SUGGESTIONS[label] for label in missing],
    )


@app.get("/products/{product_id}/readiness", response_model=ProductReadinessOut)
def product_readiness(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """商品资料完整度与开播准备状态（实时计算，不落库）。

    归属校验与商品资料接口一致：仅当前用户可见，admin 不跨用户查看。
    """
    product = get_product_for_user(db, product_id, current_user)

    filenames = [
        row[0]
        for row in db.query(ProductKnowledgeChunk.filename)
        .filter(
            ProductKnowledgeChunk.product_id == product.id,
            ProductKnowledgeChunk.user_id == current_user.id,
        )
        .distinct()
        .all()
    ]

    return ProductReadinessOut(
        completeness=_compute_product_completeness(
            product, filenames, has_chunks=bool(filenames)
        ),
        # 阶段 4 占位：开播准备清单在后续阶段实现
        prep_checklist=[],
    )


@app.get("/products/{product_id}/question-insights", response_model=ProductQuestionInsightsOut)
def product_question_insights(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """商品级问题洞察（高频问题 / 分类统计 / 最近问题 / 未覆盖问题）。

    只统计当前用户 + 当前商品，不允许跨用户、跨商品。
    """
    product = get_product_for_user(db, product_id, current_user)
    return build_question_insights(db, current_user.id, product.id)


@app.get("/products/{product_id}/ops-suggestions", response_model=ProductOpsSuggestionsOut)
def product_ops_suggestions(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """商品运营建议（资料补齐 / FAQ 候选 / 话术强化 / 风险提醒）。

    纯确定性规则生成，不调 LLM、不走向量；只统计当前用户 + 当前商品。
    """
    product = get_product_for_user(db, product_id, current_user)

    filenames = [
        row[0]
        for row in db.query(ProductKnowledgeChunk.filename)
        .filter(
            ProductKnowledgeChunk.product_id == product.id,
            ProductKnowledgeChunk.user_id == current_user.id,
        )
        .distinct()
        .all()
    ]
    completeness = _compute_product_completeness(
        product, filenames, has_chunks=bool(filenames)
    )
    return build_ops_suggestions(
        db, current_user.id, product.id, product, completeness=completeness
    )


# ─── Live review routes (直播复盘) ───


def get_live_review_for_user(db: Session, review_id: int, user: User) -> LiveReview:
    review = (
        db.query(LiveReview)
        .filter(LiveReview.id == review_id, LiveReview.user_id == user.id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    return review


@app.post("/products/{product_id}/live-reviews", response_model=LiveReviewOut)
def generate_live_review(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于商品资料与已记录运营数据生成直播复盘，不编造未统计指标。"""
    product = get_product_for_user(db, product_id, current_user)

    script_count = (
        db.query(LiveScript)
        .filter(LiveScript.product_id == product.id, LiveScript.user_id == current_user.id)
        .count()
    )
    reply_count = (
        db.query(LiveCommentReply)
        .filter(
            LiveCommentReply.product_id == product.id,
            LiveCommentReply.user_id == current_user.id,
        )
        .count()
    )
    knowledge_docs = (
        db.query(ProductKnowledgeChunk.filename)
        .filter(
            ProductKnowledgeChunk.product_id == product.id,
            ProductKnowledgeChunk.user_id == current_user.id,
        )
        .distinct()
        .count()
    )
    recent = (
        db.query(LiveCommentReply)
        .filter(
            LiveCommentReply.product_id == product.id,
            LiveCommentReply.user_id == current_user.id,
        )
        .order_by(LiveCommentReply.id.desc())
        .limit(10)
        .all()
    )
    recent_comments = "\n".join(
        f"- 评论：{r.comment.strip()[:80]}\n  回复：{(r.reply or '（无回复）').strip()[:120]}"
        for r in recent
    )

    prompt = build_live_review_prompt(
        product,
        script_count=script_count,
        reply_count=reply_count,
        knowledge_docs=knowledge_docs,
        recent_comments=recent_comments,
    )
    provider, model = resolve_llm_provider_model()
    status = "success"
    error_message = None
    content = ""

    try:
        content = call_llm(
            prompt,
            feature="live_review",
            user_id=current_user.id,
            db=db,
        )
    except Exception:
        logger.exception(
            "Live review AI call raised unexpectedly (user=%s, product=%s)",
            current_user.id,
            product_id,
        )
        content = ""

    if content and FALLBACK_MESSAGE not in content:
        status = "success"
    else:
        try:
            content = build_live_review_fallback(
                product,
                script_count=script_count,
                reply_count=reply_count,
                knowledge_docs=knowledge_docs,
                recent_comments=recent_comments,
            )
            status = "fallback"
            error_message = "AI 服务暂时不可用，已返回本地兜底复盘"
        except Exception:
            logger.exception(
                "Live review fallback generation failed (user=%s, product=%s)",
                current_user.id,
                product_id,
            )
            content = ""
            status = "failed"
            error_message = "AI 服务暂时不可用，且本地兜底复盘生成失败，请稍后重试"

    review = LiveReview(
        user_id=current_user.id,
        product_id=product.id,
        content=content,
        prompt=prompt,
        provider=provider,
        model=model,
        status=status,
        error_message=error_message,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@app.get("/products/{product_id}/live-reviews", response_model=List[LiveReviewOut])
def list_product_live_reviews(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = get_product_for_user(db, product_id, current_user)
    return (
        db.query(LiveReview)
        .filter(
            LiveReview.product_id == product.id,
            LiveReview.user_id == current_user.id,
        )
        .order_by(LiveReview.created_at.desc(), LiveReview.id.desc())
        .all()
    )


@app.get("/live-reviews/{review_id}", response_model=LiveReviewOut)
def get_live_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_live_review_for_user(db, review_id, current_user)


# ─── Dashboard stats (轻量运营看板) ───


@app.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回当前用户的轻量运营统计（不涉及直播场次/销量等未记录指标）。"""
    products = db.query(Product).filter(Product.user_id == current_user.id).count()
    live_products = (
        db.query(Product)
        .filter(Product.user_id == current_user.id, Product.live_status == "直播中")
        .count()
    )
    scripts = db.query(LiveScript).filter(LiveScript.user_id == current_user.id).count()
    replies = db.query(LiveCommentReply).filter(LiveCommentReply.user_id == current_user.id).count()
    reviews = db.query(LiveReview).filter(LiveReview.user_id == current_user.id).count()
    docs = (
        db.query(ProductKnowledgeChunk.filename)
        .filter(ProductKnowledgeChunk.user_id == current_user.id)
        .distinct()
        .count()
    )
    return DashboardStats(
        products=products,
        live_products=live_products,
        live_scripts=scripts,
        comment_replies=replies,
        live_reviews=reviews,
        knowledge_documents=docs,
    )


@app.get("/live-ops/dashboard", response_model=LiveOpsDashboard)
def live_ops_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """直播运营看板：当前用户的统计、高频评论与最近记录（不涉及未记录的直播指标）。"""
    product_count = db.query(Product).filter(Product.user_id == current_user.id).count()
    live_product_count = (
        db.query(Product)
        .filter(Product.user_id == current_user.id, Product.live_status == "直播中")
        .count()
    )
    live_script_count = (
        db.query(LiveScript).filter(LiveScript.user_id == current_user.id).count()
    )
    comment_reply_count = (
        db.query(LiveCommentReply).filter(LiveCommentReply.user_id == current_user.id).count()
    )
    live_review_count = (
        db.query(LiveReview).filter(LiveReview.user_id == current_user.id).count()
    )
    knowledge_document_count = (
        db.query(ProductKnowledgeChunk.filename)
        .filter(ProductKnowledgeChunk.user_id == current_user.id)
        .distinct()
        .count()
    )

    # 高频评论：简单按 comment.strip() 计数，不做 NLP
    all_replies = (
        db.query(LiveCommentReply)
        .filter(LiveCommentReply.user_id == current_user.id)
        .order_by(LiveCommentReply.id.desc())
        .all()
    )
    hot_questions = [
        HotQuestion(comment=comment, count=count)
        for comment, count in Counter(r.comment.strip() for r in all_replies).most_common(5)
    ]

    recent_comment_replies = all_replies[:10]
    recent_live_reviews = (
        db.query(LiveReview)
        .filter(LiveReview.user_id == current_user.id)
        .order_by(LiveReview.id.desc())
        .limit(10)
        .all()
    )

    return LiveOpsDashboard(
        product_count=product_count,
        live_product_count=live_product_count,
        live_script_count=live_script_count,
        comment_reply_count=comment_reply_count,
        live_review_count=live_review_count,
        knowledge_document_count=knowledge_document_count,
        hot_questions=hot_questions,
        recent_comment_replies=recent_comment_replies,
        recent_live_reviews=recent_live_reviews,
    )


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_product_for_user(db, product_id, current_user)


@app.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = get_product_for_user(db, product_id, current_user)

    product_data = data.model_dump()
    if not product_data.get("live_status"):
        product_data["live_status"] = "未上播"

    for key, value in product_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = get_product_for_user(db, product_id, current_user)

    db.delete(product)
    db.commit()
    return {"message": "商品已删除"}




@app.post("/rag/upload")
async def upload_rag_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    chunks = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail=f"文件过大，最大允许 {settings.MAX_UPLOAD_SIZE_MB}MB")
        chunks.append(chunk)
    data = b"".join(chunks)
    text_content = extract_text_from_upload(file, data)
    chunks = split_text(text_content)

    if not chunks:
        raise HTTPException(status_code=400, detail="文件内容为空，无法加入知识库")

    # ── Delete old vectors BEFORE SQL delete (Fix 1: avoid orphan vectors) ──
    if settings.VECTOR_SEARCH_ENABLED:
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store()
            if vs is not None:
                vs.delete_filename_chunks(current_user.id, file.filename)
        except Exception as exc:
            logger.warning(f"Vector pre-cleanup failed for '{file.filename}': {exc}")

    # 同名文件重新上传时，先删除旧片段，避免重复检索。
    db.query(DocumentChunk).filter(
        DocumentChunk.filename == file.filename,
        DocumentChunk.user_id == current_user.id,
    ).delete()

    for index, chunk in enumerate(chunks, start=1):
        db.add(DocumentChunk(
            user_id=current_user.id,
            filename=file.filename,
            chunk_index=index,
            content=chunk
        ))

    db.commit()

    # ── Vector indexing (fire-and-forget — failure does NOT fail the upload) ──
    if settings.VECTOR_SEARCH_ENABLED:
        try:
            from app.embeddings import get_embedding_service
            from app.vector_store import get_vector_store

            emb_svc = get_embedding_service()
            vs = get_vector_store()
            if vs is not None:
                # Fetch the chunks we just inserted (ordered by id to match chunk order)
                new_chunks = (
                    db.query(DocumentChunk)
                    .filter(
                        DocumentChunk.filename == file.filename,
                        DocumentChunk.user_id == current_user.id,
                    )
                    .order_by(DocumentChunk.id.asc())
                    .all()
                )
                if new_chunks:
                    texts = [c.content for c in new_chunks]
                    embeddings = emb_svc.embed_documents(texts)
                    vs.add_chunks(
                        ids=[c.id for c in new_chunks],
                        embeddings=embeddings,
                        metadatas=[
                            {
                                "user_id": c.user_id,
                                "filename": c.filename,
                                "chunk_index": c.chunk_index,
                            }
                            for c in new_chunks
                        ],
                    )
                    logger.info(
                        f"Vector indexed {len(new_chunks)} chunks for file '{file.filename}'"
                    )
        except Exception as exc:
            logger.warning(f"Vector indexing skipped (upload continues): {exc}")

    return {
        "message": "资料上传成功",
        "filename": file.filename,
        "chunks": len(chunks)
    }


@app.get("/rag/documents", response_model=List[RagDocument])
def list_rag_documents(
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.user_id == current_user.id)
    )

    # Optional filename search
    if q and q.strip():
        base = base.filter(DocumentChunk.filename.ilike(f"%{q.strip()}%"))

    rows = (
        base.with_entities(
            DocumentChunk.filename,
            func.count(DocumentChunk.id),
            func.max(DocumentChunk.created_at),
        )
        .group_by(DocumentChunk.filename)
        .all()
    )

    # Per-file vector index counts
    vs = None
    if settings.VECTOR_SEARCH_ENABLED:
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store()
        except Exception:
            pass

    result = []
    for filename, count, latest_ts in rows:
        file_indexed: Optional[int] = None
        if vs is not None and hasattr(vs, "count_file_chunks"):
            try:
                file_indexed = vs.count_file_chunks(current_user.id, filename)
            except Exception:
                pass  # Best-effort per file

        # Lightweight preview: first ~120 chars of the first chunk
        preview: Optional[str] = None
        first = (
            db.query(DocumentChunk.content)
            .filter(
                DocumentChunk.user_id == current_user.id,
                DocumentChunk.filename == filename,
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .first()
        )
        if first and first[0]:
            preview = first[0][:120]

        updated_at = latest_ts.isoformat() if latest_ts else None

        result.append(
            RagDocument(
                filename=filename,
                chunks=count,
                vector_indexed=file_indexed,
                updated_at=updated_at,
                preview=preview,
            )
        )

    return result


@app.get("/rag/documents/{filename}/chunks", response_model=RagChunkList)
def list_rag_file_chunks(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all chunks for a single file, sorted by chunk_index."""
    chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.user_id == current_user.id,
            DocumentChunk.filename == filename,
        )
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    if not chunks:
        raise HTTPException(status_code=404, detail="资料文件不存在")

    return RagChunkList(
        filename=filename,
        chunks=[
            RagChunkOut(
                chunk_index=c.chunk_index,
                content=c.content,
                created_at=c.created_at.isoformat() if c.created_at else "",
            )
            for c in chunks
        ],
    )


@app.post("/rag/documents/{filename}/reindex")
def reindex_rag_file(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reindex a single file's vector embeddings for the current user."""
    chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.user_id == current_user.id,
            DocumentChunk.filename == filename,
        )
        .order_by(DocumentChunk.id.asc())
        .all()
    )

    if not chunks:
        raise HTTPException(status_code=404, detail="资料文件不存在")

    if not settings.VECTOR_SEARCH_ENABLED:
        return {
            "reindexed": False,
            "message": "向量搜索未启用",
            "filename": filename,
            "chunks": len(chunks),
        }

    try:
        from app.embeddings import get_embedding_service
        from app.vector_store import get_vector_store

        emb_svc = get_embedding_service()
        vs = get_vector_store()
        if vs is None:
            raise RuntimeError("Vector store unavailable")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"向量服务初始化失败：{exc}")

    try:
        # Clear only this user's file's vectors
        vs.delete_filename_chunks(current_user.id, filename)

        texts = [c.content for c in chunks]
        embeddings = emb_svc.embed_documents(texts)
        vs.add_chunks(
            ids=[c.id for c in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "user_id": c.user_id,
                    "filename": c.filename,
                    "chunk_index": c.chunk_index,
                }
                for c in chunks
            ],
        )

        logger.info(
            "Reindexed %d chunks for file '%s', user %d",
            len(chunks), filename, current_user.id,
        )
        return {
            "message": f"文件 {filename} 重新索引完成，共处理 {len(chunks)} 个片段",
            "chunks": len(chunks),
            "reindexed": True,
            "filename": filename,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文件重新索引失败：{exc}")


@app.delete("/rag/documents/{filename}")
def delete_rag_document(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.filename == filename, DocumentChunk.user_id == current_user.id)
        .delete()
    )

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="资料不存在")

    db.commit()

    # ── Clean up vector store entries ──
    vector_warning: Optional[str] = None
    if settings.VECTOR_SEARCH_ENABLED:
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store()
            if vs is not None:
                vs.delete_filename_chunks(current_user.id, filename)
            else:
                vector_warning = "向量索引清理失败（向量存储不可用），索引可能不完整，建议点击「重建向量索引」"
        except Exception as exc:
            logger.error(f"Vector store cleanup failed for file '{filename}': {exc}")
            vector_warning = "向量索引清理失败，索引可能不完整，建议点击「重建向量索引」"

    resp = {
        "message": "资料已删除",
        "filename": filename,
        "deleted_chunks": deleted_count,
    }
    if vector_warning:
        resp["vector_warning"] = vector_warning
    return resp


@app.delete("/rag/documents")
def clear_rag_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.user_id == current_user.id)
        .delete()
    )
    db.commit()

    # ── Clean up vector store entries ──
    vector_warning: Optional[str] = None
    if settings.VECTOR_SEARCH_ENABLED:
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store()
            if vs is not None:
                vs.delete_user_chunks(current_user.id)
            else:
                vector_warning = "向量索引清理失败（向量存储不可用），索引可能不完整，建议点击「重建向量索引」"
        except Exception as exc:
            logger.error(f"Vector store cleanup failed for user {current_user.id}: {exc}")
            vector_warning = "向量索引清理失败，索引可能不完整，建议点击「重建向量索引」"

    resp = {
        "message": "知识库已清空",
        "deleted_chunks": deleted_count,
    }
    if vector_warning:
        resp["vector_warning"] = vector_warning
    return resp


@app.post("/rag/ask", response_model=RagAnswer)
def rag_ask(
    data: RagAsk,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = data.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    # Check that the user has at least one document uploaded
    chunk_count = (
        db.query(func.count(DocumentChunk.id))
        .filter(DocumentChunk.user_id == current_user.id)
        .scalar()
    )
    if not chunk_count:
        raise HTTPException(status_code=400, detail="请先上传产品资料或行业资料")

    retrieved = retrieve_chunks_vector(
        db, question, current_user.id, top_k=settings.VECTOR_SEARCH_TOP_K
    )
    if not retrieved:
        raise HTTPException(status_code=400, detail="知识库中没有检索到相关资料，请换个问法或上传更多资料")

    prompt = build_rag_prompt(question, retrieved)
    answer = call_llm(prompt, feature="rag_ask", user_id=current_user.id, db=db)

    return RagAnswer(
        answer=answer,
        sources=[
            RagSource(
                filename=chunk.filename,
                chunk_index=chunk.chunk_index,
                content=chunk.content[:260]
            )
            for chunk in retrieved
        ]
    )


@app.post("/rag/reindex")
def rag_reindex(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-compute embeddings for all existing chunks and re-index in the vector store.

    Safe to call multiple times — idempotent per user.
    """
    if not settings.VECTOR_SEARCH_ENABLED:
        return {"message": "向量搜索未启用", "reindexed": False, "chunks": 0}

    try:
        from app.embeddings import get_embedding_service
        from app.vector_store import get_vector_store

        emb_svc = get_embedding_service()
        vs = get_vector_store()
        if vs is None:
            raise RuntimeError("Vector store unavailable")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"向量服务初始化失败：{exc}")

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.user_id == current_user.id)
        .order_by(DocumentChunk.id.asc())
        .all()
    )
    if not chunks:
        raise HTTPException(status_code=400, detail="知识库为空，无需重新索引")

    try:
        # Clear existing vector entries for this user, then re-index
        vs.delete_user_chunks(current_user.id)

        texts = [c.content for c in chunks]
        embeddings = emb_svc.embed_documents(texts)
        vs.add_chunks(
            ids=[c.id for c in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "user_id": c.user_id,
                    "filename": c.filename,
                    "chunk_index": c.chunk_index,
                }
                for c in chunks
            ],
        )

        logger.info(f"Reindexed {len(chunks)} chunks for user {current_user.id}")
        return {
            "message": f"重新索引完成，共处理 {len(chunks)} 个片段",
            "chunks": len(chunks),
            "reindexed": True,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"重新索引失败：{exc}")




# ─── Admin: AI call logs ───


class AiCallLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    feature: str
    provider: str
    model: str
    prompt_chars: int
    response_chars: int
    estimated_prompt_tokens: int
    estimated_response_tokens: int
    status: str
    error_message: Optional[str] = None
    duration_ms: int
    created_at: str


class AiCallLogPage(BaseModel):
    items: List[AiCallLogOut]
    total: int
    page: int
    page_size: int
    pages: int


@app.get("/admin/ai-logs", response_model=AiCallLogPage)
def admin_ai_logs(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员查看 AI 调用日志（不返回 prompt 原文和 API Key）。"""
    from app.models import AiCallLog

    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)

    total = db.query(AiCallLog).count()
    pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 0
    if page > pages and total > 0:
        page = pages

    offset = (page - 1) * page_size
    rows = (
        db.query(AiCallLog)
        .order_by(AiCallLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = [
        AiCallLogOut(
            id=r.id,
            user_id=r.user_id,
            feature=r.feature,
            provider=r.provider,
            model=r.model,
            prompt_chars=r.prompt_chars,
            response_chars=r.response_chars,
            estimated_prompt_tokens=r.estimated_prompt_tokens,
            estimated_response_tokens=r.estimated_response_tokens,
            status=r.status,
            error_message=r.error_message,
            duration_ms=r.duration_ms,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]

    return AiCallLogPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
