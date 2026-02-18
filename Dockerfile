FROM python:3.14-alpine3.22

ENV PYTHON_UNBUFFERED=1
ENV PYTHONWARNINGS="ignore:Unverified HTTPS request"

# Create user and homedir
RUN set -x \
    && addgroup -g 101 -S indexer \
    && adduser -S -D -u 101 -h /home/indexer -s /sbin/nologin -G indexer -g indexer indexer

RUN apk add --no-cache --update git ca-certificates py3-yaml build-base curl

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=0

# Copy dependency files
COPY pyproject.toml uv.lock /app/
# Copy application code
COPY *.py /app/
COPY mappings /app/mappings

# Install dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked


USER 101

ENTRYPOINT ["uv", "run", "main.py"]
