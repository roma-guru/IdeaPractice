from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from journal.models import Instrument, Recording, Tag


pytestmark = pytest.mark.django_db


def test_recording_list_requires_auth(client):
    response = client.get(reverse("recording-list"))
    assert response.status_code == 302
    assert "/auth/login/" in response.url


def test_batch_upload_creates_multiple_recordings(client):
    user = get_user_model().objects.create_user(username="tester", password="secret123")
    client.login(username="tester", password="secret123")

    instrument = Instrument.objects.create(name="harmonica")
    tag = Tag.objects.create(name="rhythm", category=Tag.Category.RHYTHM)

    file_one = SimpleUploadedFile("idea-1.wav", b"RIFF....WAVE", content_type="audio/wav")
    file_two = SimpleUploadedFile("idea-2.wav", b"RIFF....WAVE", content_type="audio/wav")

    response = client.post(
        reverse("recording-upload"),
        data={
            "files": [file_one, file_two],
            "instrument": str(instrument.id),
            "tags": [str(tag.id)],
            "idea_stage": Recording.IdeaStage.PROMISING,
            "location": "home",
            "mood": "focused",
            "rating": "8",
            "is_practice": "on",
            "is_idea": "on",
            "notes": "batch test",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("recording-list")
    assert Recording.objects.count() == 2
    assert Recording.objects.filter(tags=tag).count() == 2


def test_recording_list_filter_by_stage(client):
    user = get_user_model().objects.create_user(username="tester2", password="secret123")
    client.login(username="tester2", password="secret123")

    wav = SimpleUploadedFile("one.wav", b"RIFF....WAVE", content_type="audio/wav")
    mp3 = SimpleUploadedFile("two.mp3", b"ID3", content_type="audio/mpeg")

    Recording.objects.create(file=wav, idea_stage=Recording.IdeaStage.RAW)
    Recording.objects.create(file=mp3, idea_stage=Recording.IdeaStage.DEVELOPED)

    response = client.get(reverse("recording-list"), {"stage": Recording.IdeaStage.DEVELOPED})
    assert response.status_code == 200
    recordings = list(response.context["recordings"])
    assert len(recordings) == 1
    assert Path(recordings[0].file.name).name == "two.mp3"
