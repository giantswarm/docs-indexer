FROM python:3.14-alpine3.22

ENV PYTHON_UNBUFFERED=1
ENV PYTHONWARNINGS="ignore:Unverified HTTPS request"

# Create user and homedir
RUN set -x \
    && addgroup -g 101 -S indexer \
    && adduser -S -D -u 101 -h /home/indexer -s /sbin/nologin -G indexer -g indexer indexer

RUN apk add --no-cache --update git ca-certificates py3-yaml build-base curl

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock .python-version /app/

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY *.py /app/
COPY mappings /app/mappings

USER 101

ENTRYPOINT ["uv", "run", "main.py"]
