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

# Playwright Chromium for live auto-submission.
#
# Why not `playwright install --with-deps chromium`:
#   Playwright 1.47.0 detects python:3.11-slim as Ubuntu 20.04 and tries to
#   install font packages under their Ubuntu 20.04 names (ttf-unifont,
#   ttf-ubuntu-font-family) which do not exist on Debian Bookworm. The build
#   fails with "Package '...' has no installation candidate".
#
# Fix: install Chromium's runtime dependencies manually using the correct
#   Debian Bookworm package names, then install only the browser binary
#   (playwright install chromium, no --with-deps).
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p "$PLAYWRIGHT_BROWSERS_PATH" \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       # Chromium runtime deps (Debian Bookworm package names)
       # Three packages playwright --with-deps uses have wrong names on Bookworm:
       #   libfontconfig  → libfontconfig1  (renamed)
       #   ttf-unifont    → fonts-unifont   (renamed)
       #   ttf-ubuntu-font-family → not available (Ubuntu-only, omitted)
       libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
       libcairo2 libcups2 libdbus-1-3 libdrm2 libegl1 libgbm1 \
       libglib2.0-0 libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 \
       libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
       libxext6 libxfixes3 libxkbcommon0 libxrandr2 \
       libfontconfig1 libfreetype6 libxshmfence1 \
       # Fonts (Debian Bookworm names)
       fonts-liberation fonts-noto-color-emoji fonts-unifont \
    && rm -rf /var/lib/apt/lists/* \
    && playwright install chromium

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
