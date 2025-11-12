# Use Python slim image
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY . .

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080

# Run the application
CMD ["uv", "run", "gunicorn", "app:app", "--bind", "0.0.0.0:8080"]

