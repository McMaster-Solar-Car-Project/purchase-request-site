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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY purchase_request_site/ ./purchase_request_site/
COPY run.py ./
RUN mkdir -p sessions logs static templates excel_templates && \
    cp -r purchase_request_site/static/* static/ || true && \
    cp -r purchase_request_site/templates/* templates/ || true && \
    cp -r purchase_request_site/excel_templates/* excel_templates/ || true

ENV PATH="/opt/venv/bin:$PATH"
ENV ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=80

EXPOSE 80
CMD ["python", "run.py"]