FROM python:3.11-slim
WORKDIR /app

# core engine (src/ layout)
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

# api package
COPY api/pyproject.toml /app/api/pyproject.toml
COPY api/quant_research_api /app/api/quant_research_api
COPY api/alembic /app/api/alembic
COPY api/alembic.ini /app/api/alembic.ini

RUN pip install --no-cache-dir -e /app -e /app/api

WORKDIR /app/api
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn quant_research_api.main:app --host 0.0.0.0 --port 8000"]
