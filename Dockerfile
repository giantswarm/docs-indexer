FROM python:3.9-alpine

ENV PYTHON_UNBUFFERED 1
ENV PYTHONWARNINGS "ignore:Unverified HTTPS request"

# Create user and homedir
RUN set -x \
    && addgroup -g 101 -S indexer \
    && adduser -S -D -u 101 -h /home/indexer -s /sbin/nologin -G indexer -g indexer indexer

RUN apk add --no-cache --update git ca-certificates yaml-dev build-base

ADD requirements.txt /
RUN pip install --upgrade pip && \
    pip install --global-option='--with-libyaml' pyyaml && \
    pip install -r /requirements.txt

WORKDIR /app
COPY docs_mapping.json /app/
COPY *.py /app/

USER 101

ENTRYPOINT ["python", "main.py"]
