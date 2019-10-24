default: build

build:
	docker build -t quay.io/giantswarm/docs-indexer .

run:
	docker run --rm -ti quay.io/giantswarm/docs-indexer
