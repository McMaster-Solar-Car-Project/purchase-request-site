FROM python:3.11-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies in a virtual environment
RUN uv venv /opt/venv && \
    uv pip install --no-cache-dir -r pyproject.toml --python /opt/venv/bin/python

# Production stage
FROM python:3.11-slim-bookworm AS production

# Install runtime dependencies and upgrade OpenSSL
RUN apt-get update && \
    apt-get upgrade -y openssl && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY purchase_request_site/ ./purchase_request_site/
COPY run.py ./

# Create required directories and ensure static files are properly set up
RUN mkdir -p sessions logs static templates && \
    cp -r purchase_request_site/static/* static/ || true && \
    cp -r purchase_request_site/templates/* templates/ || true

# Define build arguments for environment variables
ARG SESSION_SECRET_KEY
ARG LOGIN_EMAIL
ARG LOGIN_PASSWORD
ARG DATABASE_URL
ARG GOOGLE_SHEET_ID
ARG GOOGLE_PLACES_API_KEY
ARG GOOGLE_SETTINGS__PROJECT_ID
ARG GOOGLE_SETTINGS__PRIVATE_KEY_ID
ARG GOOGLE_SETTINGS__PRIVATE_KEY
ARG GOOGLE_SETTINGS__CLIENT_EMAIL
ARG GOOGLE_SETTINGS__CLIENT_ID
ARG GOOGLE_SETTINGS__CLIENT_X509_CERT_URL
ARG DRIVE_PARENT_FOLDER_ID
ARG SMTP_SERVER
ARG SMTP_PORT=587
ARG SMTP_USERNAME
ARG SMTP_PASSWORD
ARG ERROR_EMAIL_FROM
ARG ERROR_EMAIL_TO

# Set environment variables for production
ENV PATH="/opt/venv/bin:$PATH"
ENV ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1
ENV SESSION_SECRET_KEY=${SESSION_SECRET_KEY}
ENV LOGIN_EMAIL=${LOGIN_EMAIL}
ENV LOGIN_PASSWORD=${LOGIN_PASSWORD}
ENV DATABASE_URL=${DATABASE_URL}
ENV GOOGLE_SHEET_ID=${GOOGLE_SHEET_ID}
ENV GOOGLE_PLACES_API_KEY=${GOOGLE_PLACES_API_KEY}
ENV GOOGLE_SETTINGS__PROJECT_ID=${GOOGLE_SETTINGS__PROJECT_ID}
ENV GOOGLE_SETTINGS__PRIVATE_KEY_ID=${GOOGLE_SETTINGS__PRIVATE_KEY_ID}
ENV GOOGLE_SETTINGS__PRIVATE_KEY=${GOOGLE_SETTINGS__PRIVATE_KEY}
ENV GOOGLE_SETTINGS__CLIENT_EMAIL=${GOOGLE_SETTINGS__CLIENT_EMAIL}
ENV GOOGLE_SETTINGS__CLIENT_ID=${GOOGLE_SETTINGS__CLIENT_ID}
ENV GOOGLE_SETTINGS__CLIENT_X509_CERT_URL=${GOOGLE_SETTINGS__CLIENT_X509_CERT_URL}
ENV DRIVE_PARENT_FOLDER_ID=${DRIVE_PARENT_FOLDER_ID}
ENV SMTP_SERVER=${SMTP_SERVER}
ENV SMTP_PORT=${SMTP_PORT}
ENV SMTP_USERNAME=${SMTP_USERNAME}
ENV SMTP_PASSWORD=${SMTP_PASSWORD}
ENV ERROR_EMAIL_FROM=${ERROR_EMAIL_FROM}
ENV ERROR_EMAIL_TO=${ERROR_EMAIL_TO}
ENV DATABASE_URL=${DATABASE_URL}
ENV HOST=0.0.0.0
ENV PORT=80

# Expose the port
EXPOSE 80

# Run the application
CMD ["python", "run.py"] 