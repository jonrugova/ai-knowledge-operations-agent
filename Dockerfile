FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data /app/documents \
    && chown -R appuser:appuser /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY --chown=appuser:appuser agent.py api.py approval_store.py \
    approval_workflow.py delivery_tool.py observability.py \
    protected_actions.py semantic_search.py start.py ./
COPY --chown=appuser:appuser examples/sample_knowledge.txt \
    /app/examples/sample_knowledge.txt
COPY --from=frontend-builder --chown=appuser:appuser \
    /app/frontend/dist /app/frontend/dist

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["python", "start.py"]