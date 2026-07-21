# Production image for the Juxtapose survey app.
FROM python:3.11-slim

# Don't buffer stdout/stderr; no .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Copy the rest of the application (config, examples, etc.).
COPY . .

# Persistent data (SQLite DB + audit log) lives here. Setting DATA_DIR
# also switches the app into production mode (requires SECRET_KEY, enforces
# HTTPS cookies, refuses the default admin password).
ENV DATA_DIR=/data
VOLUME ["/data"]

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "src.survey.app:app", "--bind", "0.0.0.0:8000", "--workers", "3"]
