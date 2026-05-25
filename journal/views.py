from django.db.models import QuerySet
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import RecordingBatchUploadForm
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


@require_http_methods(["GET", "POST"])
@login_required
def recording_upload(request):
    if request.method == "POST":
        form = RecordingBatchUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_files = request.FILES.getlist("files")
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
                recording = Recording.objects.create(file=uploaded_file, **common_data)
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
