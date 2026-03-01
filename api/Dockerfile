###############################################################################
# Production image — published to Docker Hub as e3ancc/codebase-rag-api
#
# Build:  docker build -t e3ancc/codebase-rag-api:latest .
# Push:   docker push e3ancc/codebase-rag-api:latest
#
# At runtime, users supply their own environment variables
# (provider, model, API key / endpoint, etc.) via .env or -e flags.
###############################################################################
FROM python:3.12-slim AS base

# System dependencies needed at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    git \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# ---------- dependency layer (cached unless lock-file changes) ----------
COPY pyproject.toml uv.lock Makefile ./
RUN uv sync --extra treesitter-full --frozen

# ---------- application code ----------
COPY . .

# Build tree-sitter grammar submodules if vendored
RUN git config --global --add safe.directory /app && \
    (git submodule update --init --recursive --depth 1 2>/dev/null || true)

# ---------- runtime defaults ----------
# The app connects to Memgraph, Redis & Postgres via these defaults inside Docker
# They can be overridden at runtime with -e or env_file.
ENV MEMGRAPH_HOST=memgraph \
    MEMGRAPH_PORT=7687 \
    REDIS_HOST=redis \
    REDIS_PORT=6379 \
    POSTGRES_HOST=postgres \
    POSTGRES_PORT=5432 \
    POSTGRES_USER=codebase_rag \
    POSTGRES_PASSWORD=codebase_rag \
    POSTGRES_DB=codebase_rag

EXPOSE 8000

CMD ["make"]
