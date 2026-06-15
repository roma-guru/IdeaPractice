from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.db.models import Manager


def _invite_code() -> str:
    return secrets.token_urlsafe(16)  # 22-char URL-safe string


class Instrument(models.Model):
    class Family(models.TextChoices):
        STRING = "string", "String"
        KEYS = "keys", "Keys"
        SYNTH = "synth", "Synth"
        WIND = "wind", "Wind"
        BRASS = "brass", "Brass"
        PERCUSSION = "percussion", "Percussion"
        VOICE = "voice", "Voice"
        ELECTRONIC = "electronic", "Electronic"
        FIELD = "field", "Field Recording"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120, unique=True)
    family = models.CharField(
        max_length=32, choices=Family.choices, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    class Category(models.TextChoices):
        TECHNIQUE = "technique", "Technique"
        RHYTHM = "rhythm", "Rhythm"
        MOOD = "mood", "Mood"
        GENRE = "genre", "Genre"
        EXPERIMENT = "experiment", "Experiment"
        ENVIRONMENT = "environment", "Environment"

    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.EXPERIMENT)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Recording(models.Model):
    class IdeaStage(models.TextChoices):
        RAW = "raw", "Raw"
        PROMISING = "promising", "Promising"
        NEEDS_WORK = "needs_work", "Needs work"
        DEVELOPED = "developed", "Developed"
        ARCHIVED = "archived", "Archived"

    class RecordingType(models.TextChoices):
        PRACTICE = "practice", "Practice"
        IMPROVISATION = "improvisation", "Improvisation"
        COMPOSITION = "composition", "Composition"
        JAM = "jam", "Jam Session"
        LIVE = "live", "Live Performance"
        COVER = "cover", "Cover"
        DEMO = "demo", "Demo"
        IMPORTED = "imported", "Imported"

    class SunoStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    file = models.FileField(upload_to="recordings/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)
    duration = models.DurationField(null=True, blank=True)
    recording_type = models.CharField(
        max_length=20,
        choices=RecordingType.choices,
        default=RecordingType.PRACTICE,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recordings",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recordings",
    )
    location = models.CharField(max_length=200, blank=True)
    mood = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    idea_stage = models.CharField(max_length=20, choices=IdeaStage.choices, default=IdeaStage.RAW)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="recordings")
    bpm = models.FloatField(null=True, blank=True)
    key = models.CharField(max_length=16, blank=True)
    suno_status = models.CharField(
        max_length=16, choices=SunoStatus.choices, null=True, blank=True
    )
    suno_raw = models.JSONField(null=True, blank=True)

    if TYPE_CHECKING:
        shares: Manager[SharedRecording]
        comments: Manager[Comment]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        instrument = self.instrument.name if self.instrument else "No instrument"
        return f"{instrument}: {self.file.name}"


class Comment(models.Model):
    recording = models.ForeignKey(Recording, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comments",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment on recording {self.recording.pk}"


class Invite(models.Model):
    code = models.CharField(max_length=32, unique=True, default=_invite_code)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invites_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invite_used",
    )
    used_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_used(self) -> bool:
        return self.used_by_id is not None

    def __str__(self) -> str:
        status = f"used by {self.used_by}" if self.is_used else "unused"
        return f"Invite {self.code[:8]}… ({status})"


class SharedRecording(models.Model):
    recording = models.ForeignKey(Recording, on_delete=models.CASCADE, related_name="shares")
    shared_with = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_recordings",
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recordings_shared_by_me",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("recording", "shared_with")

    def __str__(self) -> str:
        return f"{self.recording} shared with {self.shared_with}"
