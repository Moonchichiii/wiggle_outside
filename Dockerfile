# Release image. ONE uvicorn worker (D21), no model key baked in (DEPLOYMENT section 3).
#
# Built on Fly's remote builder by the release runbook (DEPLOYMENT section 5), which
# records the font hashes and the image digest in docs/evidence/release.md. The frontend
# build and the fonts are part of the image rather than committed (TC-007, TC-008).

# --- Frontend build: bun only, no npm or npx (DESIGN-SPEC section 11) ----------------
FROM oven/bun:1.4.2-alpine AS frontend

WORKDIR /build
COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile

# frontend/ carries css/, img/, svg/ and fonts/. The fonts are gitignored under the
# Fontshare licence (TC-007), so they are present only when the build context supplies
# them from private storage; copying the whole directory means the build works either
# way, and without them tokens.css falls back to the system stack.
COPY frontend/ ./frontend/
COPY src/ ./src/
# The stylesheet and the board artwork (TC-008), into src/wiggle_outside/web/static/.
RUN bun run build


# --- Runtime ------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

# No build tools, no uv cache, no dev or analysis groups in the image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv

WORKDIR /app

# Runtime dependencies only, resolved from the recorded hashes.
# README.md and LICENSE come along because pyproject declares the readme and hatchling
# reads it when it builds the project, and because an Apache-2.0 image should carry its
# licence anyway.
COPY pyproject.toml uv.lock .python-version README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
# The built stylesheet, the board artwork and the fonts, from the frontend stage.
COPY --from=frontend /build/src/wiggle_outside/web/static/ ./src/wiggle_outside/web/static/
COPY --from=frontend /build/frontend/fonts/ ./frontend/fonts/
COPY docker/entrypoint.sh /usr/local/bin/wiggle-entrypoint

RUN uv sync --frozen --no-dev

# Fly mounts the volume at /data (fly.toml) owned by root. The container starts as root
# so the entrypoint can hand the mount to the app user, then drops to that user; the
# server itself never runs as root.
RUN mkdir -p /data && \
    adduser --system --no-create-home --uid 10001 wiggle && \
    chown -R wiggle:nogroup /data /app && \
    chmod 0755 /usr/local/bin/wiggle-entrypoint

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", \
         "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').read()==b'ok' else 1)"]

# One worker (D21). The model key is a runtime secret, never an image layer.
ENTRYPOINT ["/usr/local/bin/wiggle-entrypoint"]
CMD ["/app/.venv/bin/uvicorn", "wiggle_outside.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-server-header"]
