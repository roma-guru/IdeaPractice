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

from .forms import CommentForm, RecordingBatchUploadForm, RecordingEditForm, RegisterForm
from .models import Instrument, Invite, Recording, SharedRecording, Tag
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
        form = RecordingBatchUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_files = form.cleaned_data["files"]
            tags = form.cleaned_data["tags"]
            do_trim = form.cleaned_data.get("trim_silence", False)
            common_data = {
                "owner": request.user,
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
        form = RecordingBatchUploadForm()

    return render(
        request,
        "journal/recording_upload.html",
        {"form": form, "suno_enabled": settings.USE_SUNO},
    )


@login_required
def recording_list(request: HttpRequest) -> HttpResponse:
    tab = request.GET.get("tab", "my")

    if tab == "shared":
        shared_ids = SharedRecording.objects.filter(
            shared_with=request.user
        ).values_list("recording_id", flat=True)
        recordings = (
            Recording.objects.filter(pk__in=shared_ids)
            .select_related("instrument", "owner")
            .prefetch_related("tags")
        )
    else:
        tab = "my"
        recordings = (
            Recording.objects.filter(Q(owner=request.user) | Q(owner__isnull=True))
            .select_related("instrument", "owner")
            .prefetch_related("tags")
        )

    recordings = _apply_filters(recordings, request.GET)

    context = {
        "recordings": recordings,
        "instruments": Instrument.objects.all(),
        "tags": Tag.objects.all(),
        "idea_stages": Recording.IdeaStage.choices,
        "recording_types": Recording.RecordingType.choices,
        "tab": tab,
    }
    return render(request, "journal/recording_list.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def recording_detail(request: HttpRequest, pk: int) -> HttpResponse:
    recording = get_object_or_404(
        Recording.objects.select_related("instrument", "owner").prefetch_related("tags"),
        pk=pk,
    )

    is_owner = recording.owner == request.user or recording.owner is None
    has_access = is_owner or recording.shares.filter(shared_with=request.user).exists()
    if not has_access:
        raise PermissionDenied

    edit_form = RecordingEditForm(instance=recording) if is_owner else None
    comment_form = CommentForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "edit" and is_owner:
            edit_form = RecordingEditForm(request.POST, instance=recording)
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

    shared_with_users = (
        list(recording.shares.select_related("shared_with").all()) if is_owner else []
    )

    import json

    context = {
        "recording": recording,
        "edit_form": edit_form,
        "comment_form": comment_form,
        "comments": recording.comments.select_related("author").all(),
        "is_owner": is_owner,
        "shared_with_users": shared_with_users,
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
    is_owner = recording.owner == request.user or recording.owner is None
    has_access = is_owner or recording.shares.filter(shared_with=request.user).exists()
    if not has_access:
        raise PermissionDenied
    duration = recording.duration.total_seconds() if recording.duration else None
    return JsonResponse({"peaks": recording.peaks, "duration": duration})


@require_http_methods(["GET", "POST"])
@login_required
def recording_share(request: HttpRequest, pk: int) -> HttpResponse:
    recording = get_object_or_404(Recording, pk=pk)
    is_owner = recording.owner == request.user or recording.owner is None
    if not is_owner:
        raise PermissionDenied

    User = get_user_model()
    all_users = User.objects.exclude(pk=request.user.pk).order_by("username")
    currently_shared_ids = set(recording.shares.values_list("shared_with_id", flat=True))

    if request.method == "POST":
        selected_ids = {int(uid) for uid in request.POST.getlist("users") if uid.isdigit()}
        for user in all_users:
            if user.pk in selected_ids and user.pk not in currently_shared_ids:
                SharedRecording.objects.create(
                    recording=recording,
                    shared_with=user,
                    shared_by=request.user,
                )
            elif user.pk not in selected_ids and user.pk in currently_shared_ids:
                SharedRecording.objects.filter(recording=recording, shared_with=user).delete()
        return redirect("recording-detail", pk=pk)

    users_with_status = [(user, user.pk in currently_shared_ids) for user in all_users]
    return render(request, "journal/recording_share.html", {
        "recording": recording,
        "users_with_status": users_with_status,
    })


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
