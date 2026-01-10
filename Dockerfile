FROM python:3.14-alpine AS builder

# Install build dependencies
RUN apk update && apk add --no-cache \
    curl \
    libheif-dev \
    exiftool

# Install Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_CACHE=1 \
    PATH="/root/.local/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

# Set working directory
WORKDIR /offload

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --without=dev --no-interaction --no-root

# Copy application code and README
COPY offload/ ./offload/
COPY README.md ./

# Install application
RUN poetry install --without=dev --no-interaction

FROM python:3.14-alpine AS runtime

# Install runtime dependencies only
RUN apk add --no-cache \
    libheif \
    exiftool

# Set working directory
WORKDIR /offload

# Copy virtual environment from builder
COPY --from=builder /offload/.venv ./.venv
COPY offload/ ./offload/

# Set PATH to use virtual environment
ENV PATH="/offload/.venv/bin:$PATH"

# Set entrypoint
ENTRYPOINT ["offload"]
