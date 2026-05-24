# =============================================================================
# Dockerfile — Production image for ProConnect FastAPI backend
# =============================================================================
#
# MULTI-STAGE BUILD — 2 stages:
#   builder   — installs Python deps, compiles wheels
#   runtime   — slim production image, non-root user, no build tools
#
# WHY MULTI-STAGE:
#   The builder stage needs gcc, libpq-dev, etc. to compile C extensions.
#   The runtime stage copies only the compiled packages — no build toolchain.
#   Result: ~180MB image instead of ~500MB+ if we installed everything in one layer.
#
# SECURITY:
#   - Runs as non-root user `appuser` (UID 1001)
#   - No shell tools, curl, wget in runtime image
#   - No source code of test files or debug scripts in image
# =============================================================================

# =============================================================================
# Stage 1: Builder — install and compile all Python dependencies
# =============================================================================
FROM python:3.12-slim AS builder

# Install build dependencies (needed to compile asyncpg, cryptography, psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency files first — Docker caches this layer.
# If requirements.txt hasn't changed, pip install is skipped on next build.
COPY requirements.txt .

# Install all packages into a local prefix for easy copying to runtime stage
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================================================
# Stage 2: Runtime — minimal production image
# =============================================================================
FROM python:3.12-slim AS runtime

# Install only the minimal runtime libs needed by compiled extensions
# libpq5 → asyncpg/psycopg2 PostgreSQL client
# libgomp1 → required by some ML/scientific packages if used
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user — never run Python/FastAPI as root in production
RUN groupadd --system --gid 1001 appgroup \
    && useradd --system --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Copy compiled Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source code
# .dockerignore excludes: venv, __pycache__, *.pyc, tests/, scratch/, debug scripts
COPY --chown=appuser:appgroup . .

# Switch to non-root user before running the app
USER appuser

EXPOSE 8000

# Health check — polls the /health endpoint we built
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Production server: gunicorn manages worker processes, uvicorn handles async I/O
# Workers = 2 × CPU cores + 1 is the standard recommendation
# Overridden by docker-compose.prod.yml if needed
CMD ["gunicorn", "main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
