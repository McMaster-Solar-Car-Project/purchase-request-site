FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv venv /opt/venv && \
    uv pip install --no-cache-dir -r pyproject.toml --python /opt/venv/bin/python

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS production

RUN apt-get update && \
    apt-get upgrade -y openssl && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY src/ ./src/
RUN mkdir -p sessions
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]