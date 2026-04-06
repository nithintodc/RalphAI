# Multi-stage placeholder: one image per agent in production, or a single worker with ORCHESTRATOR_ROLE.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY . /app/
# COPY requirements.txt . && pip install --no-cache-dir -r requirements.txt
# Override per service (worker, cron, HTTP adapter).
CMD ["python3", "-c", "import orchestrator.flow_manager; print('orchestrator import ok')"]
