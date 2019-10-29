FROM python:3.7-alpine3.9

ENV PYTHON_UNBUFFERED 1
ENV PYTHONWARNINGS "ignore:Unverified HTTPS request"

# Create user and homedir
RUN set -x \
    && addgroup -g 101 -S indexer \
    && adduser -S -D -u 101 -h /home/indexer -s /sbin/nologin -G indexer -g indexer indexer

RUN apk add --no-cache --update git ca-certificates

ADD requirements.txt /
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

WORKDIR /app
COPY indexer.py /app/
COPY mapping.json /app/

USER 101

ENTRYPOINT ["python", "indexer.py"]
