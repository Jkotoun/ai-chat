FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.14-slim
WORKDIR /app
RUN useradd --create-home appuser \
    && mkdir -p /home/appuser/.cache/fastembed \
    && chown -R appuser /home/appuser/.cache
COPY --from=builder /app/.venv /app/.venv
COPY . .
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/home/appuser/.cache/fastembed
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
