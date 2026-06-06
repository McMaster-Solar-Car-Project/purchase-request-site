# AGENTS.md

## Package manager:

Python is managed entirely through `uv`. Do not use `pip`, `python -m venv`, or `poetry`.

Never edit `uv.lock` by hand — let `uv` regenerate it.

## Lint & format

```bash
uv run ruff check --fix
uv run ruff format
```

Config lives in `pyproject.toml`. Fix lints you introduce before finishing.

## Running the app

Do **not** start `uvicorn` directly. Use Docker:

```bash
docker compose --env-file .env up --build
```
