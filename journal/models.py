from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.db.models import Manager
from django.utils.translation import gettext_lazy as _


def _invite_code() -> str:
    return secrets.token_urlsafe(16)  # 22-char URL-safe string


class Instrument(models.Model):
    class Family(models.TextChoices):
        STRING = "string", _("String")
        KEYS = "keys", _("Keys")
        SYNTH = "synth", _("Synth")
        WIND = "wind", _("Wind")
        BRASS = "brass", _("Brass")
        PERCUSSION = "percussion", _("Percussion")
        VOICE = "voice", _("Voice")
        ELECTRONIC = "electronic", _("Electronic")
        FIELD = "field", _("Field Recording")
        OTHER = "other", _("Other")

    name = models.CharField(max_length=120, unique=True)
    family = models.CharField(max_length=32, choices=Family.choices, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    class Category(models.TextChoices):
        TECHNIQUE = "technique", _("Technique")
        RHYTHM = "rhythm", _("Rhythm")
        MOOD = "mood", _("Mood")
        GENRE = "genre", _("Genre")
        EXPERIMENT = "experiment", _("Experiment")
        ENVIRONMENT = "environment", _("Environment")

    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(
        max_length=32, choices=Category.choices, default=Category.EXPERIMENT
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Project(models.Model):
    """A collaborative music project that groups samples, clips, and DAW files."""

    name = models.CharField(max_length=255)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_projects",
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ProjectParticipant",
        through_fields=("project", "user"),
        related_name="projects",
    )
    description = models.TextField(blank=True)  # stored as HTML; render with |safe
    logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def is_participant(self, user: object) -> bool:
        return self.participants.filter(pk=getattr(user, "pk", None)).exists()


class ProjectParticipant(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participants_added",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "user")
        ordering = ["added_at"]

    def __str__(self) -> str:
        return f"{self.user} in {self.project}"


class ProjectComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_comments",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author} on {self.project}"


class Recording(models.Model):
    """An audio sample/recording. Optionally belongs to a Project."""

    class IdeaStage(models.TextChoices):
        RAW = "raw", _("Raw")
        PROMISING = "promising", _("Promising")
        NEEDS_WORK = "needs_work", _("Needs work")
        DEVELOPED = "developed", _("Developed")
        ARCHIVED = "archived", _("Archived")

    class RecordingType(models.TextChoices):
        PRACTICE = "practice", _("Practice")
        IMPROVISATION = "improvisation", _("Improvisation")
        COMPOSITION = "composition", _("Composition")
        JAM = "jam", _("Jam Session")
        LIVE = "live", _("Live Performance")
        COVER = "cover", _("Cover")
        DEMO = "demo", _("Demo")
        IMPORTED = "imported", _("Imported")

    class SunoStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSING = "processing", _("Processing")
        DONE = "done", _("Done")
        FAILED = "failed", _("Failed")
        SKIPPED = "skipped", _("Skipped")

    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="samples",
    )
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
    peaks = models.JSONField(null=True, blank=True)  # downsampled waveform for display

    if TYPE_CHECKING:
        comments: Manager[Comment]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        instrument = self.instrument.name if self.instrument else "No instrument"
        return f"{instrument}: {self.file.name}"

    def can_access(self, user: object) -> bool:
        """Owner always has access. Project participants have access if recording is in a project."""
        if self.owner_id is None or self.owner == user:
            return True
        if self.project_id and self.project.is_participant(user):
            return True
        return False


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


class Clip(models.Model):
    """Reference mp3 / audio clip attached to a project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="clips")
    file = models.FileField(upload_to="clips/%Y/%m/")
    title = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clips_uploaded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title or str(self.file)


class DAWFile(models.Model):
    """Compressed DAW project or other binary file attached to a project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="daw_files")
    file = models.FileField(upload_to="daw/%Y/%m/")
    title = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daw_files_uploaded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title or str(self.file)


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
        return self.used_by is not None

    def __str__(self) -> str:
        status = f"used by {self.used_by}" if self.is_used else "unused"
        return f"Invite {self.code[:8]}… ({status})"
