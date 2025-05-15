SHELL := /bin/bash

.PHONY: image int-test

image:
	docker build -t gsoci.azurecr.io/giantswarm/docs-indexer:latest .

int-test:
	./test/integrationtest.sh
