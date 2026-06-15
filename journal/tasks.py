from __future__ import annotations

import logging

import httpx
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _call_suno(file_url: str) -> dict:
    """POST the audio URL to the Suno API and return the parsed JSON response.

    Expected response shape::

        {
          "notes":      str,   # free-text description of the recording
          "mood":       str,   # e.g. "energetic", "melancholic"
          "tags":       [str], # suggested tag names
          "instrument": str,   # optional instrument hint
        }
    """
    resp = httpx.post(
        settings.SUNO_API_URL,
        headers={"Authorization": f"Bearer {settings.SUNO_API_KEY}"},
        json={"url": file_url},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def auto_describe_recording(self, recording_id: int) -> None:  # type: ignore[override]
    """Background task: call Suno API and populate description fields."""
    from .models import Recording, Tag

    try:
        recording = Recording.objects.get(pk=recording_id)
    except Recording.DoesNotExist:
        logger.warning("auto_describe_recording: recording %s not found", recording_id)
        return

    recording.suno_status = Recording.SunoStatus.PROCESSING
    recording.save(update_fields=["suno_status"])

    try:
        data = _call_suno(recording.file.url)

        update_fields: list[str] = ["suno_raw", "suno_status"]
        recording.suno_raw = data

        if data.get("notes") and not recording.notes:
            recording.notes = data["notes"]
            update_fields.append("notes")

        if data.get("mood") and not recording.mood:
            recording.mood = data["mood"]
            update_fields.append("mood")

        recording.suno_status = Recording.SunoStatus.DONE
        recording.save(update_fields=update_fields)

        # Apply suggested tags only when the recording has none yet
        suggested_tags: list[str] = data.get("tags") or []
        if suggested_tags and not recording.tags.exists():
            for name in suggested_tags:
                tag, _ = Tag.objects.get_or_create(
                    name=name,
                    defaults={"category": Tag.Category.EXPERIMENT},
                )
                recording.tags.add(tag)

    except Exception as exc:
        logger.exception("Suno API failed for recording %s", recording_id)
        recording.suno_status = Recording.SunoStatus.FAILED
        recording.save(update_fields=["suno_status"])
        raise self.retry(exc=exc)
