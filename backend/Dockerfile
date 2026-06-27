FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal; add build-essential only if a wheel needs compiling.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Playwright Chromium + OS deps for live auto-submission.
# Installed unconditionally — no ARG or conditional. Reason: render.yaml previously
# contained dockerBuildArgs: INSTALL_BROWSERS: "0", which Render cached in its
# service configuration and kept passing as --build-arg INSTALL_BROWSERS=0 on every
# subsequent build, overriding the Dockerfile's ARG default regardless of its value.
# Removing the ARG entirely makes the install impossible to suppress via a build arg.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p "$PLAYWRIGHT_BROWSERS_PATH" \
    && playwright install --with-deps chromium

COPY . .
RUN chmod +x entrypoint.sh

# Non-root runtime user.
RUN useradd -m appuser && chown -R appuser:appuser /app /ms-playwright
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/api/health" || exit 1

# Runs `alembic upgrade head` then launches uvicorn.
CMD ["./entrypoint.sh"]
