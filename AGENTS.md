# AGENTS.md

Project conventions for AI agents. See `CONTRIBUTING.md` for full contributor docs.

## Package manager: use `uv`

Python is managed entirely through `uv`. Do not use `pip`, `python -m venv`, or `poetry`.

```bash
uv sync                       # install/refresh deps from pyproject.toml + uv.lock
uv add <pkg>                  # add a runtime dependency
uv add --group dev <pkg>      # add a dev-only dependency
uv run <cmd>                  # run any command inside the project env
uv run pytest                 # run the tests
```

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

## Layout

- `src/` — application code (FastAPI). Routers in `src/routers/`, models in `src/models/`, settings in `src/core/settings.py`.
- `tests/` — pytest tests.
- `src/static/` and `src/templates/` — frontend assets and Jinja templates.

## Git

- Never commit directly to `main` (lefthook blocks it).
- Branch names: `feature/<short-description>` or `fix/<short-description>`.
- Commit messages: short, descriptive, dash-separated (e.g. `Fix/address-format-validation`).
- Pre-commit runs ruff + gitleaks; resolve issues rather than bypassing hooks.

## Secrets

Never commit `.env` or anything in it. If you see a real key in a file you're editing, flag it — don't propagate it.
