# Development

The recommended setup for local development is this:

1. Have [the docs docker-compose setup](https://github.com/giantswarm/docs/blob/main/docker-compose.yaml)
running.

2. Make your changes locally and build a container image, e. g.

   ```nohighlight
   docker build -t docs-indexer:dev .
   ```

3. Replace the indexer image name in `docker-compose.yaml` with the one used above (e. g. `docs-indexer:dev`)

4. Execute the indexer: `docker compose up indexer`
