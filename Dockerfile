FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

FROM base AS test
RUN pip install --no-cache-dir ".[dev]"
COPY config ./config
COPY tests ./tests
CMD ["pytest"]

FROM base AS runtime
RUN pip install --no-cache-dir .
COPY config ./config

ENTRYPOINT ["omni-healthcheck"]
CMD ["--help"]
