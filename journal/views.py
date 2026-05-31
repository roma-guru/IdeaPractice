from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, QuerySet, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import CommentForm, RecordingBatchUploadForm, RecordingEditForm
from .models import Instrument, Recording, Tag


def _apply_filters(recordings: QuerySet[Recording], params) -> QuerySet[Recording]:
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
    if kind == "idea":
        recordings = recordings.filter(is_idea=True)
    elif kind == "practice":
        recordings = recordings.filter(is_practice=True)
    if q:
        recordings = recordings.filter(notes__icontains=q)

    return recordings.distinct()


def _extract_duration(file_obj) -> timedelta | None:
    try:
        import mutagen

        file_obj.seek(0)
        audio = mutagen.File(file_obj)
        file_obj.seek(0)
        if audio and hasattr(audio, "info") and hasattr(audio.info, "length"):
            return timedelta(seconds=int(audio.info.length))
    except Exception:
        pass
    return None


@require_http_methods(["GET", "POST"])
@login_required
def recording_upload(request):
    if request.method == "POST":
        form = RecordingBatchUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_files = form.cleaned_data["files"]
            tags = form.cleaned_data["tags"]
            common_data = {
                "instrument": form.cleaned_data["instrument"],
                "idea_stage": form.cleaned_data["idea_stage"],
                "location": form.cleaned_data["location"],
                "mood": form.cleaned_data["mood"],
                "rating": form.cleaned_data["rating"],
                "is_practice": form.cleaned_data["is_practice"],
                "is_idea": form.cleaned_data["is_idea"],
                "notes": form.cleaned_data["notes"],
            }

            for uploaded_file in uploaded_files:
                duration = _extract_duration(uploaded_file)
                recording = Recording.objects.create(
                    file=uploaded_file, duration=duration, **common_data
                )
                if tags:
                    recording.tags.set(tags)
            return redirect("recording-list")
    else:
        form = RecordingBatchUploadForm()

    return render(request, "journal/recording_upload.html", {"form": form})


@login_required
def recording_list(request):
    recordings = Recording.objects.select_related("instrument").prefetch_related("tags")
    recordings = _apply_filters(recordings, request.GET)

    context = {
        "recordings": recordings,
        "instruments": Instrument.objects.all(),
        "tags": Tag.objects.all(),
        "idea_stages": Recording.IdeaStage.choices,
    }
    return render(request, "journal/recording_list.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def recording_detail(request, pk):
    recording = get_object_or_404(
        Recording.objects.select_related("instrument").prefetch_related("tags"),
        pk=pk,
    )

    edit_form = RecordingEditForm(instance=recording)
    comment_form = CommentForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "edit":
            edit_form = RecordingEditForm(request.POST, instance=recording)
            if edit_form.is_valid():
                edit_form.save()
                return redirect("recording-detail", pk=pk)
        elif action == "comment":
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.recording = recording
                comment.save()
                return redirect("recording-detail", pk=pk)

    context = {
        "recording": recording,
        "edit_form": edit_form,
        "comment_form": comment_form,
        "comments": recording.comments.all(),
    }
    return render(request, "journal/recording_detail.html", context)


@login_required
def recording_stats(request):
    by_instrument = (
        Recording.objects.values("instrument__name")
        .annotate(count=Count("id"), total_duration=Sum("duration"))
        .order_by("-count")
    )

    recent_activity = (
        Recording.objects.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("-date")[:30]
    )

    total = Recording.objects.count()
    ideas = Recording.objects.filter(is_idea=True).count()
    practice = Recording.objects.filter(is_practice=True).count()
    total_duration = Recording.objects.aggregate(total=Sum("duration"))["total"]

    context = {
        "by_instrument": by_instrument,
        "recent_activity": recent_activity,
        "total": total,
        "ideas": ideas,
        "practice": practice,
        "total_duration": total_duration,
    }
    return render(request, "journal/stats.html", context)
