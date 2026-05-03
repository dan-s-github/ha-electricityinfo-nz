# Contributing

## Setup

```bash
./scripts/setup
```

This installs pre-commit hooks for linting and commit message checks.

## Development

```bash
./scripts/develop
```

## Quality Checks

```bash
./scripts/lint
uv run --group dev pre-commit run --all-files
pytest
```
