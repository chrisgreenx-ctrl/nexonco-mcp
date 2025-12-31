# Dockerfile for Smithery deployment
# Uses uv package manager with Python 3.12

FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

# Enable bytecode compilation for performance
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy source code
COPY . /app

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Smithery sets PORT to 8081, default to 8080 for local dev
ENV PORT=8080

ENTRYPOINT []
CMD ["python", "-m", "nexonco_mcp.server"]
