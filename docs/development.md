# Development

The recommended setup for local development is this:

## Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or see the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/) for other methods.

## Setup

1. Create an `.env` file with secrets based on `.env.example`. You may find the required tokens where docs-indexer is deployed.
2. Install dependencies: `uv sync`
3. Run `make image`
4. Run `make int-test`

## Running locally

You can run the indexer locally using:

```bash
uv run main.py hugo
uv run main.py blog
```
