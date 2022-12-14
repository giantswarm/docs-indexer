default: build

build:
	docker build -t quay.io/giantswarm/docs-indexer .

run:
	docker run --rm -ti quay.io/giantswarm/docs-indexer

venv:
	virtualenv venv -p python3.9
	source venv/bin/activate
	pip install -r requirements.txt

test: venv
	venv/bin/python hugo_test.py
