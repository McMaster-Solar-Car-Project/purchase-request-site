# -------------------------------
# Builder stage
# -------------------------------
FROM python:3.13-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /install.sh
RUN chmod -R 665 /install.sh && /install.sh && rm /install.sh

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy Node.js dependencies and install
COPY package.json ./
COPY package-lock.json* ./
RUN npm install

# Copy Tailwind config
COPY tailwind.config.js* ./

# Copy source files (including input.css and templates for Tailwind scanning)
COPY src/ ./src/

# Build Tailwind CSS
RUN ./node_modules/.bin/tailwindcss -i src/input.css -o src/static/css/output.css --minify


# -------------------------------
# Production stage
# -------------------------------
FROM python:3.13-slim-bookworm AS production

RUN rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    apt-get update -o Acquire::CompressionTypes::Order::=gz && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN mkdir -p sessions
COPY src/ ./src/

# Copy the generated Tailwind CSS output from builder
COPY --from=builder /app/src/static/css/output.css ./src/static/css/output.css

EXPOSE 8000
CMD ["/opt/venv/bin/python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
