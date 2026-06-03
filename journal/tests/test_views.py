from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from journal.models import Comment, Instrument, Recording, Tag

pytestmark = pytest.mark.django_db


def test_recording_list_requires_auth(client: Client) -> None:
    response = client.get(reverse("recording-list"))
    assert response.status_code == 302
    assert "/auth/login/" in response["Location"]


def test_recording_upload_requires_auth(client: Client) -> None:
    response = client.get(reverse("recording-upload"))
    assert response.status_code == 302
    assert "/auth/login/" in response["Location"]


def test_batch_upload_creates_multiple_recordings(client: Client) -> None:
    User.objects.create_user(username="tester", password="secret123")
    client.login(username="tester", password="secret123")

    instrument = Instrument.objects.create(name="harmonica")
    tag = Tag.objects.create(name="rhythm", category=Tag.Category.RHYTHM)

    file_one = SimpleUploadedFile("idea-1.wav", b"RIFF....WAVE", content_type="audio/wav")
    file_two = SimpleUploadedFile("idea-2.wav", b"RIFF....WAVE", content_type="audio/wav")

    response = client.post(
        reverse("recording-upload"),
        data={
            "files": [file_one, file_two],
            "instrument": str(instrument.pk),
            "tags": [str(tag.pk)],
            "recording_type": Recording.RecordingType.IMPROVISATION,
            "idea_stage": Recording.IdeaStage.PROMISING,
            "location": "home",
            "mood": "focused",
            "rating": "8",
            "notes": "batch test",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("recording-list")
    assert Recording.objects.count() == 2
    assert Recording.objects.filter(tags=tag).count() == 2


def test_batch_upload_with_single_file_creates_one_recording(client: Client) -> None:
    User.objects.create_user(username="tester3", password="secret123")
    client.login(username="tester3", password="secret123")

    instrument = Instrument.objects.create(name="piano")
    file_one = SimpleUploadedFile("idea-single.wav", b"RIFF....WAVE", content_type="audio/wav")

    response = client.post(
        reverse("recording-upload"),
        data={
            "files": file_one,
            "instrument": str(instrument.pk),
            "recording_type": Recording.RecordingType.PRACTICE,
            "idea_stage": Recording.IdeaStage.RAW,
            "location": "studio",
            "mood": "calm",
            "rating": "6",
            "notes": "single file test",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("recording-list")
    assert Recording.objects.count() == 1
    saved = Recording.objects.get()
    assert Path(saved.file.name).suffix == ".wav"
    assert "idea-single" in Path(saved.file.name).stem
    assert saved.instrument == instrument
    assert saved.recording_type == Recording.RecordingType.PRACTICE


def test_batch_upload_requires_at_least_one_file(client: Client) -> None:
    User.objects.create_user(username="tester4", password="secret123")
    client.login(username="tester4", password="secret123")

    response = client.post(
        reverse("recording-upload"),
        data={
            "idea_stage": Recording.IdeaStage.RAW,
            "location": "home",
            "mood": "focused",
            "rating": "7",
            "notes": "missing files test",
        },
    )

    assert response.status_code == 200
    assert Recording.objects.count() == 0
    assert "files" in response.context["form"].errors


def test_recording_list_filter_by_stage(client: Client) -> None:
    User.objects.create_user(username="tester2", password="secret123")
    client.login(username="tester2", password="secret123")

    wav = SimpleUploadedFile("one.wav", b"RIFF....WAVE", content_type="audio/wav")
    mp3 = SimpleUploadedFile("two.mp3", b"ID3", content_type="audio/mpeg")

    Recording.objects.create(file=wav, idea_stage=Recording.IdeaStage.RAW)
    Recording.objects.create(file=mp3, idea_stage=Recording.IdeaStage.DEVELOPED)

    response = client.get(reverse("recording-list"), {"stage": Recording.IdeaStage.DEVELOPED})
    assert response.status_code == 200
    recordings = list(response.context["recordings"])
    assert len(recordings) == 1
    assert recordings[0].idea_stage == Recording.IdeaStage.DEVELOPED
    assert Path(recordings[0].file.name).suffix == ".mp3"


def test_recording_detail_requires_auth(client: Client) -> None:
    wav = SimpleUploadedFile("auth.wav", b"RIFF....WAVE", content_type="audio/wav")
    recording = Recording.objects.create(file=wav)
    response = client.get(reverse("recording-detail", args=[recording.pk]))
    assert response.status_code == 302
    assert "/auth/login/" in response["Location"]


def test_recording_detail_get(client: Client) -> None:
    User.objects.create_user(username="detail_user", password="secret123")
    client.login(username="detail_user", password="secret123")

    instrument = Instrument.objects.create(name="banjo")
    wav = SimpleUploadedFile("detail.wav", b"RIFF....WAVE", content_type="audio/wav")
    recording = Recording.objects.create(file=wav, instrument=instrument, notes="test note")

    response = client.get(reverse("recording-detail", args=[recording.pk]))
    assert response.status_code == 200
    assert response.context["recording"] == recording
    assert "edit_form" in response.context
    assert "comment_form" in response.context


def test_recording_detail_edit(client: Client) -> None:
    User.objects.create_user(username="edit_user", password="secret123")
    client.login(username="edit_user", password="secret123")

    instrument = Instrument.objects.create(name="sitar")
    wav = SimpleUploadedFile("edit.wav", b"RIFF....WAVE", content_type="audio/wav")
    recording = Recording.objects.create(file=wav, idea_stage=Recording.IdeaStage.RAW)

    response = client.post(
        reverse("recording-detail", args=[recording.pk]),
        data={
            "action": "edit",
            "instrument": str(instrument.pk),
            "recording_type": Recording.RecordingType.PRACTICE,
            "idea_stage": Recording.IdeaStage.PROMISING,
            "location": "studio",
            "mood": "calm",
            "notes": "updated notes",
        },
    )

    assert response.status_code == 302
    recording.refresh_from_db()
    assert recording.idea_stage == Recording.IdeaStage.PROMISING
    assert recording.instrument == instrument
    assert recording.notes == "updated notes"


def test_recording_detail_add_comment(client: Client) -> None:
    User.objects.create_user(username="comment_user", password="secret123")
    client.login(username="comment_user", password="secret123")

    wav = SimpleUploadedFile("comment.wav", b"RIFF....WAVE", content_type="audio/wav")
    recording = Recording.objects.create(file=wav)

    response = client.post(
        reverse("recording-detail", args=[recording.pk]),
        data={"action": "comment", "text": "try a different rhythm"},
    )

    assert response.status_code == 302
    assert Comment.objects.filter(recording=recording).count() == 1
    assert Comment.objects.get(recording=recording).text == "try a different rhythm"


def test_recording_stats_requires_auth(client: Client) -> None:
    response = client.get(reverse("recording-stats"))
    assert response.status_code == 302
    assert "/auth/login/" in response["Location"]


def test_recording_stats_get(client: Client) -> None:
    User.objects.create_user(username="stats_user", password="secret123")
    client.login(username="stats_user", password="secret123")

    instrument = Instrument.objects.create(name="duduk")
    wav = SimpleUploadedFile("stat.wav", b"RIFF....WAVE", content_type="audio/wav")
    Recording.objects.create(
        file=wav, instrument=instrument, recording_type=Recording.RecordingType.IMPROVISATION
    )

    response = client.get(reverse("recording-stats"))
    assert response.status_code == 200
    assert response.context["total"] == 1
    by_type = {row["recording_type"]: row["count"] for row in response.context["by_type"]}
    assert by_type.get(Recording.RecordingType.IMPROVISATION) == 1


def test_recording_list_filters_by_multiple_params(client: Client) -> None:
    User.objects.create_user(username="tester5", password="secret123")
    client.login(username="tester5", password="secret123")

    guitar = Instrument.objects.create(name="guitar")
    piano = Instrument.objects.create(name="keyboard")
    ambient = Tag.objects.create(name="ambient", category=Tag.Category.MOOD)
    rhythm = Tag.objects.create(name="syncopated", category=Tag.Category.RHYTHM)

    match = Recording.objects.create(
        file=SimpleUploadedFile("match.wav", b"RIFF....WAVE", content_type="audio/wav"),
        instrument=guitar,
        idea_stage=Recording.IdeaStage.PROMISING,
        recording_type=Recording.RecordingType.IMPROVISATION,
        notes="ambient texture from rainy evening",
    )
    match.tags.add(ambient)

    practice_rec = Recording.objects.create(
        file=SimpleUploadedFile("practice.wav", b"RIFF....WAVE", content_type="audio/wav"),
        instrument=guitar,
        idea_stage=Recording.IdeaStage.PROMISING,
        recording_type=Recording.RecordingType.PRACTICE,
        notes="ambient rhythm practice",
    )
    practice_rec.tags.add(ambient, rhythm)

    other_instrument = Recording.objects.create(
        file=SimpleUploadedFile("keys.wav", b"RIFF....WAVE", content_type="audio/wav"),
        instrument=piano,
        idea_stage=Recording.IdeaStage.PROMISING,
        recording_type=Recording.RecordingType.IMPROVISATION,
        notes="ambient texture for keys",
    )
    other_instrument.tags.add(ambient)

    response = client.get(
        reverse("recording-list"),
        {
            "instrument": str(guitar.pk),
            "tag": str(ambient.pk),
            "kind": Recording.RecordingType.IMPROVISATION,
            "q": "texture",
        },
    )

    assert response.status_code == 200
    recordings = list(response.context["recordings"])
    assert [r.pk for r in recordings] == [match.pk]
