FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Fix Python symlinks in venv to point to distroless Python 3.11
RUN rm -f /offload/.venv/bin/python* && \
    ln -s /usr/bin/python /offload/.venv/bin/python && \
    ln -s /usr/bin/python /offload/.venv/bin/python3 && \
    ln -s /usr/bin/python /offload/.venv/bin/python3.11

FROM gcr.io/distroless/python3-debian12 AS runtime

# Set working directory
WORKDIR /offload

# Copy virtual environment from builder
COPY --from=builder /offload/.venv /offload/.venv
COPY --from=builder /offload/offload /offload/offload

# Set entrypoint
ENTRYPOINT ["/offload/.venv/bin/offload"]
