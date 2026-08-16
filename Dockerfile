# ── Frontend build (Vue3 + Vite) — 产物供运行镜像作为默认演示入口 ──
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# ── Base dependencies ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── PostgreSQL driver (lightweight, no harm for SQLite deployments) ──
COPY requirements-db-pg.txt .
RUN pip install --no-cache-dir -r requirements-db-pg.txt

# ── Vector search (ChromaDB for SQLite mode) ──
COPY requirements-vector.txt .
RUN pip install --no-cache-dir -r requirements-vector.txt

# ── App code ──
COPY app ./app
COPY static ./static
# V5：Vue3 前端构建产物（默认演示入口）；旧 static/index.html 保留为 /legacy 回退入口
COPY --from=frontend-build /build/dist ./frontend/dist

# ── Defaults for Docker deployment ──
# EMBEDDING_PROVIDER=openai_compatible is the recommended Docker default
# because local embedding requires sentence-transformers + PyTorch (~2.5 GB).
# Set EMBEDDING_PROVIDER=local and use Dockerfile.local if you need local models.
ENV EMBEDDING_PROVIDER=openai_compatible

EXPOSE 8000

# ── Health check (使用 Python 标准库，无需额外系统依赖) ──
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
