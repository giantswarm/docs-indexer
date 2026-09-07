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
| resources.requests.ephemeralStorage | string | `"512Mi"` | Ephemeral storage request. The `docs-cache` `emptyDir` holds a full git clone of the indexed repository, so this has to cover the largest one. |
| resources.limits.cpu | string | `"200m"` |  |
| resources.limits.memory | string | `"200M"` |  |
| resources.limits.ephemeralStorage | string | `"2Gi"` | Ephemeral storage limit. Exceeding it evicts the pod mid-run, so this leaves room for the indexed repositories to grow. |
| credentials.githubAccessToken | string | `"DUMMYTOKEN"` |  |
| credentials.hubspotAccessToken | string | `"DUMMYTOKEN"` |  |
| architecture | string | `""` | Target CPU architecture for the indexer jobs. Empty imposes no constraint. `arm64` pins them to arm64 nodes, adding both the `kubernetes.io/arch` node selector and the toleration for the `kubernetes.io/arch=arm64:NoSchedule` taint that Giant Swarm arm64 node pools carry. Both are required, so this single value sets both. |
| nodeSelector | object | `{}` | Node selector for the indexer jobs. Merged with `architecture`. Pinning to arm64 here rather than through `architecture` also adds the arm64 taint toleration, so either route is safe. A value that contradicts `architecture` fails the render. |
| tolerations | list | `[]` | Tolerations for the indexer jobs. Merged with the toleration that `architecture: arm64` adds. |
