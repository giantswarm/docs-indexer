FROM python:2.7-alpine
ENV PYTHON_UNBUFFERED 1
RUN apk add --update git && rm -rf /var/cache/apk/*
RUN pip install BeautifulSoup==3.2.1 Markdown==2.3.1 elasticsearch==1.9.0 toml==0.8.2
WORKDIR /app
ADD . /app/
ENTRYPOINT ["python", "indexer.py"]
