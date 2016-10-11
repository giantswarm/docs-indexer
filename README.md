# docs-indexer

Indexes content for the search engine of [docs.giantswarm.io](https://docs.giantswarm.io).

As a source, this takes a public GitHub repository. As a target, an Elasticsearch API endpoint is used.

## Configuration

The following environment variables are supported for configuration:

- `REPOSITORY_URL`: Git repo URL to clone, e. g. `https://github.com/giantswarm/docs-content.git`
- `REPOSITORY_BRANCH`: Defaults to `master`
- `REPOSITORY_SUBFOLDER`: Only look into this path within the repository for indexable content
- `EXTERNAL_REPOSITORY_SUBFOLDER`: Only look into this path within external repositories for indexable content
- `KEEP_PROCESS_ALIVE`: If set, the process keeps running (sleeping forever) when the job is finished.
- `ELASTICSEARCH_ENDPOINT`: URI for the Elasticsearch API endpoint
- `ELASTICSEARCH_INDEX_NAME`: Name for the index to create. Defaults to `docs`.
- `ELASTICSEARCH_DOCTYPE`: Name for the document type to use. Defaults to `page`.

The search mapping for the documents created can be found in `mapping.json`.
