[![Docker Repository on Quay](https://quay.io/repository/giantswarm/docs-indexer/status "Docker Repository on Quay")](https://quay.io/repository/giantswarm/docs-indexer)

# docs-indexer

Indexes content for the search engine of [docs.giantswarm.io](https://docs.giantswarm.io/).

As a source, this takes a public GitHub repository. As a target, an Elasticsearch API endpoint is used.

## App

There is a helm chart in the `helm` subfolder.

## Configuration

The following environment variables are supported for configuration:

- `REPOSITORY_BRANCH`: Defaults to `master`
- `REPOSITORY_SUBFOLDER`: Only look into this path within the repository for indexable content
- `KEEP_PROCESS_ALIVE`: If set, the process keeps running (sleeping forever) when the job is finished.
- `ELASTICSEARCH_ENDPOINT`: URI for the Elasticsearch API endpoint
- `APIDOCS_BASE_URI`: Base URI for API documentation. Should be `https://docs.giantswarm.io/api/`.
- `APIDOCS_BASE_PATH`: Should be `/api/`
- `API_SPEC_FILES`: Comma separated list of YAML files to fetch for the OpenAPI spec

The search mapping for the documents created can be found in `docs_mapping.json`.

## Usage

[This docker-compose configuration](https://github.com/giantswarm/docs/blob/master/docker-compose.yaml)
shows how to use the container.

## Elasticsearch schema

This indexer creates an Elasticsearch index with the mapping defined in the file `docs_mapping.json`.

Here is some additional information on the index fields:

- `uri`: The URI of the page, starting with a slash (/), so not containing schema or hostname. Used as unique identifier, so there cannot be two entries with the same `uri` value.
- `breadcrumb`: List field for breadcrumb items. For a page with `uri = "/foo/bar/"` this will be `["foo", "bar"]`.
- `breadcrumb_1` to `breadcrumb_n`: Individual fields for the first, second, third, ... nth breadcrumb item.
- `title`: The title of the document, as intended for representation as a main headline of a search result item. If a document provides several titles, this is supposed to be what users would consider the main headline of the article, or what contains the most valuable content to search for.
- `body`: All text from the main page, excluding the first headline (which is expected to resemble the `title` content).
- `text`: catch-all field. Used for generic search queries where no specific field is selected for a match.
