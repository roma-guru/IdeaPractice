from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile
from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import (
    ClipUploadForm,
    CommentForm,
    DAWFileUploadForm,
    ProjectCommentForm,
    ProjectForm,
    RecordingBatchUploadForm,
    RecordingEditForm,
    RegisterForm,
)
from .models import Clip, DAWFile, Instrument, Invite, Project, ProjectParticipant, Recording, Tag
from .tasks import analyse_recording, auto_describe_recording

logger = logging.getLogger(__name__)


def _apply_filters(recordings: QuerySet[Recording], params: QueryDict) -> QuerySet[Recording]:
    instrument = params.get("instrument")
    tag = params.get("tag")
    stage = params.get("stage")
    kind = params.get("kind")
    q = params.get("q")

    if instrument:
        recordings = recordings.filter(instrument_id=instrument)
    if tag:
        recordings = recordings.filter(tags__id=tag)
    if stage:
        recordings = recordings.filter(idea_stage=stage)
    if kind:
        recordings = recordings.filter(recording_type=kind)
    if q:
        recordings = recordings.filter(notes__icontains=q)

    return recordings.distinct()


def _trim_silence(file_obj: UploadedFile) -> UploadedFile:
    """
    Remove leading and trailing silence using ffmpeg's silenceremove filter.
    Returns the original file unchanged if ffmpeg is not available or fails.
    Threshold: -50 dB, minimum silence duration: 0.5 s.
    """
    name = file_obj.name or "audio.wav"
    suffix = Path(name).suffix or ".wav"
    tmp_in_path: str | None = None
    tmp_out_path: str | None = None

    try:
        file_obj.seek(0)
        raw = file_obj.read()

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
            tmp_in.write(raw)
            tmp_in_path = tmp_in.name

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_out:
            tmp_out_path = tmp_out.name

        # Double-reverse trick: trim leading silence → reverse → trim again → reverse back.
        af = (
            "silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB,"
            "areverse,"
            "silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB,"
            "areverse"
        )
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-af", af, tmp_out_path],
            capture_output=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.warning("ffmpeg silence trim failed: %s", result.stderr.decode(errors="replace"))
        else:
            with open(tmp_out_path, "rb") as fh:
                content = fh.read()
            if content:
                return InMemoryUploadedFile(
                    file=io.BytesIO(content),
                    field_name=None,
                    name=name,
                    content_type=getattr(file_obj, "content_type", "audio/mpeg"),
                    size=len(content),
                    charset=None,
                )
    except FileNotFoundError:
        logger.warning("ffmpeg not found; skipping silence trim")
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg timed out trimming %s", name)
    except Exception:
        logger.exception("Unexpected error during silence trim for %s", name)
    finally:
        for path in filter(None, [tmp_in_path, tmp_out_path]):
            try:
                os.unlink(path)
            except OSError:
                pass

    file_obj.seek(0)
    return file_obj


def _extract_duration(file_obj: UploadedFile) -> timedelta | None:
    try:
        from mutagen import File as MutagenFile  # type: ignore[attr-defined]

        file_obj.seek(0)
        audio = MutagenFile(file_obj)
        file_obj.seek(0)
        if audio and hasattr(audio, "info") and hasattr(audio.info, "length"):
            return timedelta(seconds=int(audio.info.length))
    except Exception:
        pass
    return None


@require_http_methods(["GET", "POST"])
@login_required
def recording_upload(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = RecordingBatchUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            uploaded_files = form.cleaned_data["files"]
            tags = form.cleaned_data["tags"]
            do_trim = form.cleaned_data.get("trim_silence", False)
            common_data = {
                "owner": request.user,
                "project": form.cleaned_data.get("project"),
                "instrument": form.cleaned_data["instrument"],
                "recording_type": form.cleaned_data["recording_type"],
                "idea_stage": form.cleaned_data["idea_stage"],
                "location": form.cleaned_data["location"],
                "mood": form.cleaned_data["mood"],
                "rating": form.cleaned_data["rating"],
                "notes": form.cleaned_data["notes"],
            }

            do_describe = form.cleaned_data.get("auto_describe", False)
            for uploaded_file in uploaded_files:
                if do_trim:
                    uploaded_file = _trim_silence(uploaded_file)
                duration = _extract_duration(uploaded_file)
                recording = Recording.objects.create(
                    file=uploaded_file, duration=duration, **common_data
                )
                if tags:
                    recording.tags.set(tags)
                analyse_recording.delay(recording.pk)  # type: ignore[union-attr]
                if settings.USE_SUNO and do_describe:
                    auto_describe_recording.delay(recording.pk)  # type: ignore[union-attr]
                    recording.suno_status = Recording.SunoStatus.PENDING
                    recording.save(update_fields=["suno_status"])
            return redirect("recording-list")
    else:
        form = RecordingBatchUploadForm(user=request.user)

    return render(
        request,
        "journal/recording_upload.html",
        {"form": form, "suno_enabled": settings.USE_SUNO},
    )


@login_required
def recording_list(request: HttpRequest) -> HttpResponse:
    recordings = (
        Recording.objects.filter(Q(owner=request.user) | Q(owner__isnull=True))
        .select_related("instrument", "owner", "project")
        .prefetch_related("tags")
    )
    recordings = _apply_filters(recordings, request.GET)

    context = {
        "recordings": recordings,
        "instruments": Instrument.objects.all(),
        "tags": Tag.objects.all(),
        "idea_stages": Recording.IdeaStage.choices,
        "recording_types": Recording.RecordingType.choices,
    }
    return render(request, "journal/recording_list.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def recording_detail(request: HttpRequest, pk: int) -> HttpResponse:
    recording = get_object_or_404(
        Recording.objects.select_related("instrument", "owner", "project").prefetch_related("tags"),
        pk=pk,
    )

    if not recording.can_access(request.user):
        raise PermissionDenied

    is_owner = recording.owner == request.user or recording.owner is None
    edit_form = RecordingEditForm(instance=recording, user=request.user) if is_owner else None
    comment_form = CommentForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "edit" and is_owner:
            edit_form = RecordingEditForm(request.POST, instance=recording, user=request.user)
            if edit_form.is_valid():
                edit_form.save()
                return redirect("recording-detail", pk=pk)
        elif action == "comment":
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.recording = recording
                comment.author = request.user
                comment.save()
                return redirect("recording-detail", pk=pk)

    import json

    context = {
        "recording": recording,
        "edit_form": edit_form,
        "comment_form": comment_form,
        "comments": recording.comments.select_related("author").all(),
        "is_owner": is_owner,
        "peaks_json": json.dumps(recording.peaks) if recording.peaks else None,
        "duration_s": (
            recording.duration.total_seconds() if recording.duration else None
        ),
    }
    return render(request, "journal/recording_detail.html", context)


@login_required
def recording_peaks(request: HttpRequest, pk: int) -> JsonResponse:
    """Return pre-computed waveform peaks for a recording (used by list-page player)."""
    recording = get_object_or_404(Recording, pk=pk)
    if not recording.can_access(request.user):
        raise PermissionDenied
    duration = recording.duration.total_seconds() if recording.duration else None
    return JsonResponse({"peaks": recording.peaks, "duration": duration})


@require_http_methods(["GET", "POST"])
def register(request: HttpRequest, code: str) -> HttpResponse:
    try:
        invite = Invite.objects.get(code=code)
    except Invite.DoesNotExist:
        return render(request, "registration/register.html", {"invalid": True})

    if invite.is_used:
        return render(request, "registration/register.html", {"exhausted": True})

    form = RegisterForm(request.POST if request.method == "POST" else None)
    if form and form.is_valid():
        User = get_user_model()
        user = User.objects.create_user(  # type: ignore[union-attr]
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password1"],
        )
        invite.used_by = user
        invite.used_at = timezone.now()
        invite.save()
        login(request, user)
        return redirect("recording-list")

    return render(request, "registration/register.html", {"form": form, "invite": invite})


@login_required
def recording_stats(request: HttpRequest) -> HttpResponse:
    user_recordings = Recording.objects.filter(
        Q(owner=request.user) | Q(owner__isnull=True)
    )

    by_instrument = (
        user_recordings.values("instrument__name")
        .annotate(count=Count("id"), total_duration=Sum("duration"))
        .order_by("-count")
    )

    recent_activity = (
        user_recordings.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("-date")[:30]
    )

    total = user_recordings.count()
    total_duration = user_recordings.aggregate(total=Sum("duration"))["total"]

    by_type = (
        user_recordings.values("recording_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    context = {
        "by_instrument": by_instrument,
        "by_type": by_type,
        "recent_activity": recent_activity,
        "total": total,
        "total_duration": total_duration,
        "recording_types": {v: label for v, label in Recording.RecordingType.choices},
    }
    return render(request, "journal/stats.html", context)


# ── Project views ──────────────────────────────────────────────────────────────


@login_required
def project_list(request: HttpRequest) -> HttpResponse:
    projects = (
        Project.objects.filter(participants=request.user)
        .select_related("creator")
        .prefetch_related("memberships__user")
        .annotate(sample_count=Count("samples", distinct=True))
    )
    return render(request, "journal/project_list.html", {"projects": projects})


@require_http_methods(["GET", "POST"])
@login_required
def project_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.creator = request.user
            project.save()
            # Auto-add creator as first participant
            ProjectParticipant.objects.create(
                project=project, user=request.user, added_by=request.user
            )
            return redirect("project-detail", pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, "journal/project_create.html", {"form": form})


@require_http_methods(["GET", "POST"])
@login_required
def project_detail(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk)

    if not project.is_participant(request.user):
        raise PermissionDenied

    is_creator = project.creator_id == request.user.pk

    clip_form = ClipUploadForm()
    daw_form = DAWFileUploadForm()
    comment_form = ProjectCommentForm()
    edit_form = ProjectForm(instance=project) if is_creator else None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "comment":
            comment_form = ProjectCommentForm(request.POST)
            if comment_form.is_valid():
                c = comment_form.save(commit=False)
                c.project = project
                c.author = request.user
                c.save()
                return redirect("project-detail", pk=pk)

        elif action == "upload_clip":
            clip_form = ClipUploadForm(request.POST, request.FILES)
            if clip_form.is_valid():
                Clip.objects.create(
                    project=project,
                    file=clip_form.cleaned_data["file"],
                    title=clip_form.cleaned_data["title"],
                    notes=clip_form.cleaned_data["notes"],
                    uploaded_by=request.user,
                )
                return redirect("project-detail", pk=pk)

        elif action == "upload_daw":
            daw_form = DAWFileUploadForm(request.POST, request.FILES)
            if daw_form.is_valid():
                DAWFile.objects.create(
                    project=project,
                    file=daw_form.cleaned_data["file"],
                    title=daw_form.cleaned_data["title"],
                    notes=daw_form.cleaned_data["notes"],
                    uploaded_by=request.user,
                )
                return redirect("project-detail", pk=pk)

        elif action == "add_participant" and is_creator:
            User = get_user_model()
            username = request.POST.get("username", "").strip()
            try:
                user = User.objects.get(username=username)
                if user != request.user:
                    ProjectParticipant.objects.get_or_create(
                        project=project,
                        user=user,
                        defaults={"added_by": request.user},
                    )
            except User.DoesNotExist:
                pass
            return redirect("project-detail", pk=pk)

        elif action == "remove_participant" and is_creator:
            user_id = request.POST.get("user_id", "")
            if user_id.isdigit() and int(user_id) != request.user.pk:
                ProjectParticipant.objects.filter(
                    project=project, user_id=int(user_id)
                ).delete()
            return redirect("project-detail", pk=pk)

        elif action == "edit" and is_creator:
            edit_form = ProjectForm(request.POST, request.FILES, instance=project)
            if edit_form.is_valid():
                edit_form.save()
                return redirect("project-detail", pk=pk)

        return redirect("project-detail", pk=pk)

    context = {
        "project": project,
        "samples": project.samples.select_related("instrument", "owner").prefetch_related("tags"),
        "clips": project.clips.select_related("uploaded_by"),
        "daw_files": project.daw_files.select_related("uploaded_by"),
        "comments": project.comments.select_related("author"),
        "participants": project.memberships.select_related("user", "added_by"),
        "is_creator": is_creator,
        "clip_form": clip_form,
        "daw_form": daw_form,
        "comment_form": comment_form,
        "edit_form": edit_form,
    }
    return render(request, "journal/project_detail.html", context)
