# CLAUDE.md
This file provides guidance to Claude Code and contributors working in this repository.

## Project overview
- Name: Idea Practice Tracker
- Stack: Django 5, Python (see `pyproject.toml`), pytest, ruff
- Main apps/packages:
  - `config/` — Django project configuration (`settings.py`, `urls.py`, ASGI/WSGI)
  - `journal/` — core application (models, views, forms, admin, urls)
  - `templates/` — shared templates

## Environment and setup
Use `uv` for dependency management and command execution.

Install runtime + dev dependencies:

```bash
uv sync --group dev
```

## Common development commands
Run Django dev server:

```bash
uv run python manage.py runserver
```

Run database migrations:

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
```

Run tests:

```bash
uv run pytest
```

Run linting and auto-fixes:

```bash
uv run ruff check .
uv run ruff check . --fix
```

## Testing notes
- Pytest is configured in `pyproject.toml`.
- `DJANGO_SETTINGS_MODULE` is `config.settings`.
- Coverage is enabled by default and outputs `coverage.xml`.

## Storage configuration
Media storage defaults to local files in `media/`.
S3-compatible storage can be enabled with environment variables (see `README.md` for full list), including:
- `USE_S3=true`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_ENDPOINT_URL`

## Code conventions
- Keep changes focused and minimal.
- Follow ruff style rules configured in `pyproject.toml`.
- Preserve Django app boundaries (`config` for project config, `journal` for domain logic).
- Add or update tests for behavior changes whenever possible.
