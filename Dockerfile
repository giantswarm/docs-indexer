FROM python:2.7-alpine3.6
ENV PYTHON_UNBUFFERED 1
RUN apk add --update git && rm -rf /var/cache/apk/*
RUN pip install BeautifulSoup==3.2.1 Markdown==2.3.1 elasticsearch==1.9.0 toml==0.8.2 prance==0.8.0
WORKDIR /app
COPY indexer.py /app/
COPY mapping.json /app/
ENTRYPOINT ["python", "indexer.py"]
