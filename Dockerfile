FROM python:3.13-alpine3.21

ENV PYTHON_UNBUFFERED=1
ENV PYTHONWARNINGS="ignore:Unverified HTTPS request"

# Create user and homedir
RUN set -x \
    && addgroup -g 101 -S indexer \
    && adduser -S -D -u 101 -h /home/indexer -s /sbin/nologin -G indexer -g indexer indexer

RUN apk add --no-cache --update git ca-certificates py3-yaml build-base

ADD requirements.txt /
RUN pip install --upgrade pip && \
    pip install -r /requirements.txt

WORKDIR /app
COPY *.py /app/
COPY mappings /app/mappings

USER 101

ENTRYPOINT ["python", "main.py"]
