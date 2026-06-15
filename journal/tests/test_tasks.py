from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from journal.models import Recording, Tag
from journal.tasks import analyse_recording, auto_describe_recording

pytestmark = pytest.mark.django_db


def _wav() -> SimpleUploadedFile:
    return SimpleUploadedFile("t.wav", b"RIFF....WAVE", content_type="audio/wav")


def _recording(**kwargs: object) -> Recording:
    owner = User.objects.create_user(username="owner_t", password="x") if "owner" not in kwargs else kwargs.pop("owner")  # type: ignore[assignment]
    return Recording.objects.create(file=_wav(), owner=owner, **kwargs)  # type: ignore[arg-type]


SUNO_RESPONSE = {
    "notes": "A bluesy improvisation in E minor",
    "mood": "melancholic",
    "tags": ["blues", "improvisation"],
    "instrument": "guitar",
}

SUNO_SETTINGS = {
    "USE_SUNO": True,
    "SUNO_API_KEY": "test-key",
    "SUNO_API_URL": "https://api.suno.example/describe",
}


# ── upload view integration ────────────────────────────────────────────────

@override_settings(**SUNO_SETTINGS)
def test_upload_with_auto_describe_sets_pending(client: Client) -> None:
    user = User.objects.create_user(username="uploader", password="pw")
    client.force_login(user)

    with (
        patch("journal.views.analyse_recording"),
        patch("journal.views.auto_describe_recording") as mock_suno,
    ):
        client.post(
            reverse("recording-upload"),
            data={
                "files": _wav(),
                "recording_type": Recording.RecordingType.PRACTICE,
                "idea_stage": Recording.IdeaStage.RAW,
                "auto_describe": "on",
            },
        )
        assert mock_suno.delay.call_count == 1

    rec = Recording.objects.get(owner=user)
    assert rec.suno_status == Recording.SunoStatus.PENDING


@override_settings(USE_SUNO=False)
def test_upload_without_flag_does_not_enqueue(client: Client) -> None:
    user = User.objects.create_user(username="uploader2", password="pw")
    client.force_login(user)

    with (
        patch("journal.views.analyse_recording"),
        patch("journal.views.auto_describe_recording") as mock_suno,
    ):
        client.post(
            reverse("recording-upload"),
            data={
                "files": _wav(),
                "recording_type": Recording.RecordingType.PRACTICE,
                "idea_stage": Recording.IdeaStage.RAW,
                "auto_describe": "on",
            },
        )
        mock_suno.delay.assert_not_called()

    rec = Recording.objects.get(owner=user)
    assert rec.suno_status is None


# ── task unit tests ────────────────────────────────────────────────────────

@override_settings(**SUNO_SETTINGS)
def test_task_populates_notes_mood_and_tags() -> None:
    owner = User.objects.create_user(username="task_owner1", password="x")
    rec = Recording.objects.create(file=_wav(), owner=owner)

    with patch("journal.tasks._call_suno", return_value=SUNO_RESPONSE):
        auto_describe_recording(rec.pk)

    rec.refresh_from_db()
    assert rec.suno_status == Recording.SunoStatus.DONE
    assert rec.notes == "A bluesy improvisation in E minor"
    assert rec.mood == "melancholic"
    assert rec.suno_raw == SUNO_RESPONSE
    tag_names = list(rec.tags.values_list("name", flat=True))
    assert "blues" in tag_names
    assert "improvisation" in tag_names


@override_settings(**SUNO_SETTINGS)
def test_task_does_not_overwrite_existing_notes() -> None:
    owner = User.objects.create_user(username="task_owner2", password="x")
    rec = Recording.objects.create(file=_wav(), owner=owner, notes="my own note", mood="happy")

    with patch("journal.tasks._call_suno", return_value=SUNO_RESPONSE):
        auto_describe_recording(rec.pk)

    rec.refresh_from_db()
    assert rec.notes == "my own note"
    assert rec.mood == "happy"


@override_settings(**SUNO_SETTINGS)
def test_task_does_not_overwrite_existing_tags() -> None:
    owner = User.objects.create_user(username="task_owner3", password="x")
    existing_tag = Tag.objects.create(name="ambient", category=Tag.Category.MOOD)
    rec = Recording.objects.create(file=_wav(), owner=owner)
    rec.tags.add(existing_tag)

    with patch("journal.tasks._call_suno", return_value=SUNO_RESPONSE):
        auto_describe_recording(rec.pk)

    rec.refresh_from_db()
    tag_names = list(rec.tags.values_list("name", flat=True))
    # Original tag kept, Suno tags NOT added (recording already had tags)
    assert "ambient" in tag_names
    assert "blues" not in tag_names


@override_settings(**SUNO_SETTINGS)
def test_task_marks_failed_on_http_error() -> None:
    import httpx

    owner = User.objects.create_user(username="task_owner4", password="x")
    rec = Recording.objects.create(file=_wav(), owner=owner)

    # Patch retry so it doesn't loop; we only care that suno_status is set to FAILED
    with patch("journal.tasks._call_suno", side_effect=httpx.HTTPError("timeout")):
        with patch.object(auto_describe_recording, "retry", side_effect=httpx.HTTPError("timeout")):
            with pytest.raises(httpx.HTTPError):
                auto_describe_recording(rec.pk)

    rec.refresh_from_db()
    assert rec.suno_status == Recording.SunoStatus.FAILED


@override_settings(**SUNO_SETTINGS)
def test_task_is_noop_for_missing_recording() -> None:
    # Should not raise; just log and return
    auto_describe_recording(99999)


@override_settings(**SUNO_SETTINGS)
def test_upload_form_shows_auto_describe_when_suno_enabled(client: Client) -> None:
    user = User.objects.create_user(username="form_check", password="pw")
    client.force_login(user)
    response = client.get(reverse("recording-upload"))
    assert response.status_code == 200
    assert response.context["suno_enabled"] is True
    assert b"auto_describe" in response.content


@override_settings(USE_SUNO=False)
def test_upload_form_hides_auto_describe_when_suno_disabled(client: Client) -> None:
    user = User.objects.create_user(username="form_check2", password="pw")
    client.force_login(user)
    response = client.get(reverse("recording-upload"))
    assert response.status_code == 200
    assert response.context["suno_enabled"] is False
    assert b"auto_describe" not in response.content


# ── analyse_recording task ─────────────────────────────────────────────────

def _make_owner(name: str = "owner_a") -> User:
    return User.objects.create_user(username=name, password="x")


def test_analyse_sets_bpm_and_key() -> None:
    import numpy as np

    owner = _make_owner("analyse1")
    rec = Recording.objects.create(file=_wav(), owner=owner)

    fake_y = np.zeros(22050)
    with (
        patch("journal.tasks.librosa.load", return_value=(fake_y, 22050)),
        patch("journal.tasks.librosa.beat.beat_track", return_value=(np.float64(120.0), None)),
        patch("journal.tasks._detect_key", return_value="A minor"),
    ):
        analyse_recording(rec.pk)

    rec.refresh_from_db()
    assert rec.bpm == 120.0
    assert rec.key == "A minor"


def test_analyse_does_not_overwrite_existing_bpm_and_key() -> None:
    import numpy as np

    owner = _make_owner("analyse2")
    rec = Recording.objects.create(file=_wav(), owner=owner, bpm=95.0, key="G major")

    fake_y = np.zeros(22050)
    with (
        patch("journal.tasks.librosa.load", return_value=(fake_y, 22050)),
        patch("journal.tasks.librosa.beat.beat_track", return_value=(np.float64(120.0), None)),
        patch("journal.tasks._detect_key", return_value="A minor"),
    ):
        analyse_recording(rec.pk)

    rec.refresh_from_db()
    assert rec.bpm == 95.0   # unchanged
    assert rec.key == "G major"  # unchanged


def test_analyse_is_noop_for_missing_recording() -> None:
    analyse_recording(99999)  # must not raise


def test_upload_always_enqueues_analyse(client: Client) -> None:
    user = User.objects.create_user(username="enqueue_check", password="pw")
    client.force_login(user)

    with patch("journal.views.analyse_recording") as mock_analyse:
        client.post(
            reverse("recording-upload"),
            data={
                "files": _wav(),
                "recording_type": Recording.RecordingType.PRACTICE,
                "idea_stage": Recording.IdeaStage.RAW,
            },
        )
        assert mock_analyse.delay.call_count == 1


def test_bpm_key_editable_via_detail_form(client: Client) -> None:
    owner = User.objects.create_user(username="edit_bpm", password="pw")
    rec = Recording.objects.create(file=_wav(), owner=owner)
    client.force_login(owner)

    response = client.post(
        reverse("recording-detail", args=[rec.pk]),
        data={
            "action": "edit",
            "recording_type": Recording.RecordingType.PRACTICE,
            "idea_stage": Recording.IdeaStage.RAW,
            "bpm": "128.0",
            "key": "D minor",
        },
    )
    assert response.status_code == 302
    rec.refresh_from_db()
    assert rec.bpm == 128.0
    assert rec.key == "D minor"
