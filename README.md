[![Docker Repository on Quay](https://quay.io/repository/giantswarm/docs-indexer/status "Docker Repository on Quay")](https://quay.io/repository/giantswarm/docs-indexer)

# docs-indexer

Indexes content for the search engine available in [docs.giantswarm.io](https://docs.giantswarm.io/).

It covers:

- Documentation ([docs.giantswarm.io](https://docs.giantswarm.io/))
  - REST API documentation ([docs.giantswarm.io/api/](https://docs.giantswarm.io/api/))
- Blog posts ([www.giantswarm.io/blog](https://www.giantswarm.io/blog))

## App

There is a helm chart in the `helm` subfolder.

Note: A separate secret is required for the `HUBSPOT_API_KEY` environment variable:

```yaml
apiVersion: v1
kind: Secret
type: Opaque
metadata:
  name: hubspot-api-key
  namespace: docs
  labels:
    app: docs-indexer
data:
  hubspot-api-key: REDACTED
```

## Configuration

The following environment variables are required for configuration:

- `ELASTICSEARCH_ENDPOINT`: URI for the Elasticsearch API endpoint
- `HUBSPOT_API_KEY`: Hubspot API key for blog indexing.

These environment varilables may be set in order to override defaults, especially for development:

- `REPOSITORY_BRANCH`: Defaults to `main`
- `REPOSITORY_SUBFOLDER`: Only look into this path within the repository for indexable content
- `APIDOCS_BASE_URI`: Base URI for API documentation. Should be `https://docs.giantswarm.io/api/`.
- `APIDOCS_BASE_PATH`: Should be `/api/`
- `API_SPEC_FILES`: Comma separated list of YAML files to fetch for the OpenAPI spec

## Usage

[This docker-compose configuration](https://github.com/giantswarm/docs/blob/main/docker-compose.yaml)
shows how to use the container.

## Elasticsearch schema

This indexers create Elasticsearch indices with the mappings defined in the files `mappings/*.json`.

Here is some additional information on the index fields:

- `uri`: The URI of the page, starting with a slash (/), so not containing schema or hostname. Used as unique identifier, so there cannot be two entries with the same `uri` value.
- `breadcrumb`: List field for breadcrumb items. For a page with `uri = "/foo/bar/"` this will be `["foo", "bar"]`.
- `breadcrumb_1` to `breadcrumb_n`: Individual fields for the first, second, third, ... nth breadcrumb item.
- `title`: The title of the document, as intended for representation as a main headline of a search result item. If a document provides several titles, this is supposed to be what users would consider the main headline of the article, or what contains the most valuable content to search for.
- `body`: All text from the main page, excluding the first headline (which is expected to resemble the `title` content).
- `text`: catch-all field. Used for generic search queries where no specific field is selected for a match.
- `date`: Publish date or last modification date for the entry.
- `image_uri`: URL of an image for the entry (optional).
