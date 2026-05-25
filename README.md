# Idea Practice Tracker

## S3-Compatible Media Storage

By default, uploads are stored locally in `media/`.

To enable S3-compatible storage (AWS S3, Backblaze B2 S3 API, MinIO, Cloudflare R2, etc.), set:

```env
USE_S3=true
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-east-1
AWS_S3_ENDPOINT_URL=https://s3.your-provider.com
AWS_S3_ADDRESSING_STYLE=path
AWS_S3_SIGNATURE_VERSION=s3v4
```

Optional:

```env
AWS_S3_CUSTOM_DOMAIN=cdn.example.com
```

If `AWS_S3_CUSTOM_DOMAIN` is set, media URLs will use it.

## Tooling (uv + ruff + pytest)

Install runtime + dev tools:

```bash
uv sync --group dev
```

Run lint/format checks:

```bash
uv run ruff check .
uv run ruff check . --fix
```

Run tests:

```bash
uv run pytest
```

Faster test execution on multi-core machines:

```bash
uv run pytest -n auto
```

Coverage is enabled by default via `pyproject.toml` (`--cov` options in pytest config).
A machine-readable report is emitted as `coverage.xml`.
