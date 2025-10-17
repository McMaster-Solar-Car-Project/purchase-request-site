# -------------------------------
# Builder stage
# -------------------------------
FROM python:3.13-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /install.sh
RUN chmod -R 665 /install.sh && /install.sh && rm /install.sh

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen


# -------------------------------
# Production stage
# -------------------------------
FROM python:3.13-slim-bookworm AS production

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY src/ ./src/
RUN mkdir -p sessions

EXPOSE 8000
CMD ["/opt/venv/bin/python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
