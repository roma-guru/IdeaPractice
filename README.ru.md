# Idea Practice Tracker

**Журнал аудиопрактики и идей** — рабочий журнал живых записей, а не просто библиотека файлов. Загружайте записи с рекордера, разбивайте по инструментам и стадиям идей, ищите материал и отслеживайте статистику практики.

## Что умеет

- Загрузка аудиофайлов (пакетная, с фоновой синхронизацией в облако)
- Каталогизация по инструменту, тегам, настроению, стадии идеи
- Статистика практики: записей по инструментам, общее время, активность по дням
- Превью формы волны с предвычисленными пиками (без проблем с декодированием MP3)
- Комментарии к записям для заметок о развитии идеи
- Мультипользовательский режим с регистрацией по приглашениям и шарингом
- Автоописание через ИИ (опционально, требует `USE_SUNO=true`)

## Ключевые концепции

**Стадии идеи** — то, что превращает систему из архива в рабочий инструмент:

| Стадия | Значение |
|---|---|
| `raw` | Свежая запись, ещё не оценена |
| `promising` | Стоит развивать |
| `needs_work` | Есть потенциал, но требует доработки |
| `developed` | Активно разрабатывается |
| `archived` | Сохранена, но не активна |

**Типы записей:** идея, практика, полевая запись, эксперимент, кавер, композиция

**Категории тегов:** техника, ритм, настроение, жанр, эксперимент, окружение

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SECRET_KEY` | dev key | Секретный ключ Django |
| `DEBUG` | `true` | Установить `false` в продакшне |
| `ALLOWED_HOSTS` | `*` | Хосты через запятую |
| `CSRF_TRUSTED_ORIGINS` | — | Origins через запятую (например, `https://your-app.railway.app`) |
| `DATABASE_URL` | SQLite | URL подключения к Postgres (Railway подставляет автоматически) |

### S3-совместимое хранилище медиа

По умолчанию файлы хранятся локально в `media/`. Для включения S3-совместимого хранилища (AWS S3, Backblaze B2, MinIO, Cloudflare R2 и др.):

```env
USE_S3=true
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-east-1
AWS_S3_ENDPOINT_URL=https://s3.your-provider.com
AWS_S3_ADDRESSING_STYLE=path
AWS_S3_SIGNATURE_VERSION=s3v4
AWS_S3_CUSTOM_DOMAIN=cdn.example.com   # опционально
```

### Celery / фоновые задачи

BPM, определение тональности и пики формы волны вычисляются в воркере Celery после загрузки:

```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Автоописание через Suno AI (опционально)

```env
USE_SUNO=true
SUNO_API_KEY=your-key
SUNO_API_URL=https://your-ai-endpoint/describe
```

## Установка

```bash
uv sync --group dev
uv run python manage.py migrate
uv run python manage.py runserver
```

Запустить сервер и воркер Celery вместе:

```bash
uv run python manage.py rundev
```

## Разработка

```bash
uv run ruff check .                      # линтер
uv run ruff check . --fix                # линтер + автоисправление
uv run pytest                            # тесты (покрытие включено по умолчанию)
uv run pytest -n auto                    # параллельные тесты на многоядерных машинах
uv run python manage.py check_all        # django check + ruff + pytest + pyright
```

Отчёт о покрытии выводится в терминал и сохраняется в `coverage.xml`.

## Деплой (Railway)

1. Запушить на GitHub; подключить репозиторий к Railway
2. Railway автоматически обнаруживает `Procfile` — фаза `release` запускает миграции + collectstatic + compilemessages, фаза `web` — gunicorn
3. Добавить аддон Postgres — Railway автоматически подставит `DATABASE_URL`
4. Задать переменные: `SECRET_KEY`, `DEBUG=false`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
5. Создать суперпользователя через Shell в дашборде Railway:
   ```bash
   python manage.py createsuperuser
   ```

## Языки

Интерфейс доступен на английском, русском, греческом и испанском. Переключение — через иконку глобуса в правом верхнем углу, выбор сохраняется в cookie.
