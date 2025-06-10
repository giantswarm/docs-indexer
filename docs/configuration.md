# Configuration

The indexers are configured entirely via **environment variables**.

The following environment variables are accepted, by indexer sub command:

## `hugo`

- `ELASTICSEARCH_ENDPOINT`: URI for the Elasticsearch API endpoint.
- `GITHUB_TOKEN`: If the repo is private, use this access token.
- `INDEX_NAME`: Name of the search index to maintain.
- `BASE_URL`: URL corresponding to the published root page of the site.
- `REPOSITORY_HANDLE`: Github organization and repository name in the format `org/repo`.
- `REPOSITORY_BRANCH`: Defaults to `main`.
- `REPOSITORY_SUBFOLDER`: Only look into this path within the repository for indexable content.
- `TYPE_LABEL`: User friendly search result type name.

## `blog`

- `HUBSPOT_ACCESS_TOKEN`: Hubspot Private App access token (must have at least the scope `content`).
