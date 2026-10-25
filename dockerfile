FROM --platform=linux/amd64 python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.txt pyproject.toml README.md ./
RUN mkdir -p src/research_and_analyst
COPY src/research_and_analyst/__init__.py src/research_and_analyst/
RUN pip install --no-cache-dir --user --default-timeout=120 --retries 10 torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --user --default-timeout=120 --retries 10 -r requirements.txt
RUN pip install --no-cache-dir --user --default-timeout=120 --retries 10 https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl

FROM --platform=linux/amd64 python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libmagic1 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
COPY . .
RUN mkdir -p /app/src/generated_report /app/logs /app/static
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV PYTHONPATH=/app/src
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "research_and_analyst.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
