from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import httpx
import librosa
import numpy as np
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Key detection helpers ──────────────────────────────────────────────────
# Krumhansl-Schmuckler key profiles
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _detect_key(y: np.ndarray, sr: int) -> str:
    import librosa

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    scores = [
        (float(np.corrcoef(np.roll(_KS_MAJOR, i), chroma)[0, 1]), f"{_NOTE_NAMES[i]} major")
        for i in range(12)
    ] + [
        (float(np.corrcoef(np.roll(_KS_MINOR, i), chroma)[0, 1]), f"{_NOTE_NAMES[i]} minor")
        for i in range(12)
    ]
    return max(scores, key=lambda x: x[0])[1]


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyse_recording(self, recording_id: int) -> None:  # type: ignore[override]
    """Detect BPM and musical key with librosa; always runs after upload."""
    from .models import Recording

    try:
        recording = Recording.objects.get(pk=recording_id)
    except Recording.DoesNotExist:
        logger.warning("analyse_recording: recording %s not found", recording_id)
        return

    suffix = Path(recording.file.name).suffix or ".wav"
    tmp_path: str | None = None
    try:
        with recording.file.open("rb") as fh:
            content = fh.read()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        y, sr = librosa.load(tmp_path, sr=None, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        key = _detect_key(y, sr)

        update_fields: list[str] = []
        if not recording.bpm:
            recording.bpm = round(float(tempo), 1)
            update_fields.append("bpm")
        if not recording.key:
            recording.key = key
            update_fields.append("key")
        if update_fields:
            recording.save(update_fields=update_fields)

    except Exception as exc:
        logger.exception("analyse_recording failed for recording %s", recording_id)
        raise self.retry(exc=exc)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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
