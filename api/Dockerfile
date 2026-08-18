# The API service. Holds the model key, the compiled evidence, and the agent loop.
# The web tier holds none of those, which is the point of the split.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Repo-shaped layout so path resolution is identical in the container and on a laptop.
WORKDIR /repo/api

COPY api/pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY api/ ./
COPY evidence/ /repo/evidence/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
