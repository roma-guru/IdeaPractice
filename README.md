# Idea Practice Tracker

**Audio Practice & Idea Journal** — a working journal for live recordings, not just a file library. Upload from a recorder, tag by instrument and idea stage, search your material, and track practice analytics.

## What it does

- Upload audio files (batch, with background cloud sync)
- Catalogue by instrument, tags, mood, idea stage
- Track practice stats: recordings per instrument, total time, activity by day
- Waveform preview with pre-computed peaks (no Web Audio decode issues)
- Comments on recordings for development notes
- Multi-user with invite-based registration and sharing
- Auto-describe via AI (optional, requires `USE_SUNO=true`)

## Core concepts

**Idea stages** — what turns this from a file archive into a working tool:

| Stage | Meaning |
|---|---|
| `raw` | Fresh capture, not yet evaluated |
| `promising` | Worth developing |
| `needs_work` | Has potential but needs revision |
| `developed` | Actively worked on |
| `archived` | Preserved but not active |

**Recording types:** idea, practice, field recording, experiment, cover, composition

**Tag categories:** technique, rhythm, mood, genre, experiment, environment

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | dev key | Django secret key |
| `DEBUG` | `true` | Set to `false` in production |
| `ALLOWED_HOSTS` | `*` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | — | Comma-separated origins (e.g. `https://your-app.railway.app`) |
| `DATABASE_URL` | SQLite | Postgres connection URL (Railway injects this automatically) |

### S3-compatible media storage

By default, uploads are stored locally in `media/`. To enable S3-compatible storage (AWS S3, Backblaze B2, MinIO, Cloudflare R2, etc.):

```env
USE_S3=true
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-east-1
AWS_S3_ENDPOINT_URL=https://s3.your-provider.com
AWS_S3_ADDRESSING_STYLE=path
AWS_S3_SIGNATURE_VERSION=s3v4
AWS_S3_CUSTOM_DOMAIN=cdn.example.com   # optional
```

### Celery / background tasks

BPM, key detection, and waveform peaks are computed in a Celery worker after upload:

```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Suno AI auto-description (optional)

```env
USE_SUNO=true
SUNO_API_KEY=your-key
SUNO_API_URL=https://your-ai-endpoint/describe
```

## Setup

```bash
uv sync --group dev
uv run python manage.py migrate
uv run python manage.py runserver
```

Run server + Celery worker together:

```bash
uv run python manage.py rundev
```

## Development

```bash
uv run ruff check .                      # lint
uv run ruff check . --fix                # lint + autofix
uv run pytest                            # tests (coverage enabled by default)
uv run pytest -n auto                    # parallel tests on multi-core
uv run python manage.py check_all        # django check + ruff + pytest + pyright
```

Coverage outputs `coverage.xml` and a terminal report.

## Deployment (Railway)

1. Push to GitHub; connect repo to Railway
2. Railway auto-detects `Procfile` — `release` phase runs migrations + collectstatic + compilemessages, `web` phase starts gunicorn
3. Add a Postgres addon — Railway injects `DATABASE_URL` automatically
4. Set env vars: `SECRET_KEY`, `DEBUG=false`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
5. Create a superuser via the Railway dashboard shell:
   ```bash
   python manage.py createsuperuser
   ```

## Languages

UI is available in English, Russian, Greek, and Spanish. Language is switched via the globe icon in the top-right corner and persisted in a cookie.
