from __future__ import annotations

from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.core.files import File
from django.utils.translation import gettext_lazy as _

from .models import Comment, Instrument, Project, ProjectComment, Recording, Tag


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data: Any, initial: File | None = None) -> list[File]:
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            if not data:
                raise forms.ValidationError(self.error_messages["required"], code="required")
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


class RecordingBatchUploadForm(forms.Form):
    files = MultipleFileField(  # type: ignore[assignment]
        widget=MultipleFileInput(),
        help_text=_("Select one or more recordings."),
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        required=False,
        help_text=_("Assign to a project (required for sharing with collaborators)."),
    )
    instrument = forms.ModelChoiceField(queryset=Instrument.objects.all(), required=False)
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    recording_type = forms.ChoiceField(
        choices=Recording.RecordingType.choices,
        initial=Recording.RecordingType.PRACTICE,
    )
    idea_stage = forms.ChoiceField(
        choices=Recording.IdeaStage.choices, initial=Recording.IdeaStage.RAW
    )
    location = forms.CharField(max_length=200, required=False)
    mood = forms.CharField(max_length=120, required=False)
    rating = forms.IntegerField(min_value=0, max_value=10, required=False)
    trim_silence = forms.BooleanField(
        required=False,
        label=_("Trim silence"),
        help_text=_("Remove leading and trailing silence (requires ffmpeg)."),
    )
    auto_describe = forms.BooleanField(
        required=False,
        label=_("Auto-describe"),
        help_text=_("Use Suno AI to suggest notes, mood, and tags (requires USE_SUNO)."),
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args: Any, user: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["project"].queryset = Project.objects.filter(  # type: ignore[union-attr]
                participants=user
            )


_KEY_CHOICES = [("", "—")] + [
    (f"{note} {mode}", f"{note} {mode}")
    for mode in ("major", "minor")
    for note in ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
]


class RecordingEditForm(forms.ModelForm):  # type: ignore[type-arg]
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    key = forms.ChoiceField(choices=_KEY_CHOICES, required=False)

    class Meta:
        model = Recording
        fields = [
            "project",
            "instrument",
            "recording_type",
            "tags",
            "idea_stage",
            "location",
            "mood",
            "rating",
            "bpm",
            "key",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args: Any, user: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["project"].queryset = Project.objects.filter(  # type: ignore[union-attr]
                participants=user
            )
        else:
            self.fields["project"].queryset = Project.objects.all()  # type: ignore[union-attr]
        self.fields["project"].required = False  # type: ignore[union-attr]


class ProjectForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Project
        fields = ["name", "description", "logo"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
        }
        help_texts = {
            "description": _("HTML is rendered as-is. Use for rich links and formatting."),
        }


class ProjectCommentForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = ProjectComment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={"rows": 3, "placeholder": _("Notes, ideas, feedback for the project…")}
            )
        }
        labels = {"text": _("Add a comment")}


class ClipUploadForm(forms.Form):
    file = forms.FileField(label=_("File (mp3, wav, …)"))
    title = forms.CharField(max_length=255, required=False, label=_("Title"))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class DAWFileUploadForm(forms.Form):
    file = forms.FileField(label=_("File (zip, als, flp, …)"))
    title = forms.CharField(max_length=255, required=False, label=_("Title"))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput())
    password2 = forms.CharField(label=_("Confirm password"), widget=forms.PasswordInput())

    def clean_username(self) -> str:
        username = self.cleaned_data["username"]
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(_("This username is already taken."))
        return username

    def clean(self) -> dict[str, Any]:
        data: dict[str, Any] = super().clean() or {}
        p1 = data.get("password1")
        p2 = data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_("Passwords do not match."))
        return data


class CommentForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={"rows": 3, "placeholder": _("What to try next, what didn't work, ideas...")}
            )
        }
        labels = {"text": _("Add a comment")}
