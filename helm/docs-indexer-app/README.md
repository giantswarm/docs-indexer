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
| architecture | string | `""` | Target CPU architecture for the indexer jobs. Empty imposes no constraint. `arm64` pins them to arm64 nodes, adding both the `kubernetes.io/arch` node selector and the toleration for the `kubernetes.io/arch=arm64:NoSchedule` taint that Giant Swarm arm64 node pools carry. Both are required, so this single value sets both. |
| nodeSelector | object | `{}` | Node selector for the indexer jobs. Merged with `architecture`. Pinning to arm64 here rather than through `architecture` also adds the arm64 taint toleration, so either route is safe. A value that contradicts `architecture` fails the render. |
| tolerations | list | `[]` | Tolerations for the indexer jobs. Merged with the toleration that `architecture: arm64` adds. |
