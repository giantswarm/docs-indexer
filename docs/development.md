# Development

The recommended setup for local development is this:

1. Create an `.env` file with secrets based on `.env.example`. You may find the required tokens where docs-indexer is deployed.

2. Run `make image`

3. Run `make int-test`

Alternatively you can execute the same test [via the GitHub web UI](https://github.com/giantswarm/docs-indexer/actions/workflows/integration-test.yaml).
