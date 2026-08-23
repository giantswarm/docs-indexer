# docs-indexer-app

Indexes content for the docs search engine.

**Homepage:** <https://github.com/giantswarm/docs-indexer>

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| name | string | `"docs-indexer-app"` |  |
| namespace | string | `"docs"` |  |
| image.registry | string | `"gsoci.azurecr.io"` |  |
| image.name | string | `"docs-indexer"` |  |
| image.tag | string | `""` |  |
| opensearchEndpoint | string | `"http://sitesearch-app:9200/"` |  |
| resources.requests.cpu | string | `"100m"` |  |
| resources.requests.memory | string | `"80M"` |  |
| resources.limits.cpu | string | `"200m"` |  |
| resources.limits.memory | string | `"200M"` |  |
| credentials.githubAccessToken | string | `"DUMMYTOKEN"` |  |
| credentials.hubspotAccessToken | string | `"DUMMYTOKEN"` |  |
