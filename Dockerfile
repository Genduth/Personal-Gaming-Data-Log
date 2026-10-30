# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system gamevault && adduser --system --ingroup gamevault gamevault

COPY --chown=gamevault:gamevault pyproject.toml README.md LICENSE ./
COPY --chown=gamevault:gamevault src ./src
COPY --chown=gamevault:gamevault database ./database

RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then \
      PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir .; \
    else \
      pip install --no-cache-dir .; \
    fi

USER gamevault
EXPOSE 8000

CMD ["sh", "-c", "python -m gamevault.migrate && uvicorn gamevault.main:app --host 0.0.0.0 --port 8000"]
