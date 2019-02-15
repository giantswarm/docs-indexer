FROM python:3.7-alpine3.9

ENV PYTHON_UNBUFFERED 1
ENV PYTHONWARNINGS "ignore:Unverified HTTPS request"

RUN apk add --update git && rm -rf /var/cache/apk/*

ADD requirements.txt /
RUN pip install -r /requirements.txt

WORKDIR /app
COPY indexer.py /app/
COPY mapping.json /app/
ENTRYPOINT ["python", "indexer.py"]
