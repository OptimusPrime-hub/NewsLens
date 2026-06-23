FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-ansi && \
    python -m spacy download en_core_web_sm

COPY . .

RUN mkdir -p data/pathway_sources logs

EXPOSE 8000 8765

CMD ["uvicorn", "src.m5_ui.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
