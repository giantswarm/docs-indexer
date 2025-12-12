# Search content indexer

This repository contains search indexers for Giant Swarm's search engines, both internal (intranet) and public ([docs](https://docs.giantswarm.io/), [handbook](https://handbook.giantswarm.io/)).

Apart from some shared code, the code is mainly structured by content source, and there is a dedicated subcommand for each source:

- `hugo`: HUGO sites (for docs, intranet, handbook)
- `blog`: Hubspot blog articles

## Development

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management. See the [development documentation](docs/development.md) for setup instructions.

## Documentation

See the [docs](docs/) folder for additional documentation.
