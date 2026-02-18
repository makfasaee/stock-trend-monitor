FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY pyproject.toml ./
COPY stockwatch/__init__.py stockwatch/__init__.py

# Install dependencies (no dev extras in prod)
RUN uv pip install --system --no-cache -e .

# Copy source
COPY . .

# Data directories (overridden by Docker volumes in production)
RUN mkdir -p data logs reports

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "stockwatch"]
CMD ["scheduler"]
