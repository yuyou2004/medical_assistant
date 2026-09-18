# API 服务镜像：uv 安装依赖 + uvicorn 启动
# 构建：docker build -t medical-api -f docker/Dockerfile .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 先拷贝依赖清单并安装（利用 Docker 层缓存，代码变更不用重装依赖）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 拷贝应用代码（.dockerignore 排除 PDF 与向量库）
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY README.md ./

# 运行时用虚拟环境里的 uvicorn，端口 8000
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
