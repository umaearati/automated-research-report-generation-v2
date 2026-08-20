# Multi-stage build for Research Report Generation System
FROM --platform=linux/amd64 python:3.11-slim AS builder
WORKDIR /app
# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*
# Copy dependency files
COPY requirements.txt .
COPY pyproject.toml .
COPY README.md .
# Create package structure for editable install
RUN mkdir -p src/research_and_analyst
COPY src/research_and_analyst/__init__.py src/research_and_analyst/
# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt
# ----------------------------
# Final runtime stage
# ----------------------------
FROM --platform=linux/amd64 python:3.11-slim
WORKDIR /app
# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*
# Copy installed Python packages from builder
COPY --from=builder /root/.local /root/.local
# Copy full application source
COPY . .
# Create directories for reports, logs, and static files
RUN mkdir -p /app/src/generated_report /app/logs /app/static
# Set environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV PYTHONPATH=/app/src
# Expose the API port
EXPOSE 8000
# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
# Start the FastAPI app
CMD ["uvicorn", "research_and_analyst.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
