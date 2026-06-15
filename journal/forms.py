from __future__ import annotations

from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.core.files import File

from .models import Comment, Instrument, Recording, Tag


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
        help_text="Select one or more recordings.",
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
    idea_stage = forms.ChoiceField(choices=Recording.IdeaStage.choices, initial=Recording.IdeaStage.RAW)
    location = forms.CharField(max_length=200, required=False)
    mood = forms.CharField(max_length=120, required=False)
    rating = forms.IntegerField(min_value=0, max_value=10, required=False)
    trim_silence = forms.BooleanField(
        required=False,
        label="Trim silence",
        help_text="Remove leading and trailing silence (requires ffmpeg).",
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))


class RecordingEditForm(forms.ModelForm):  # type: ignore[type-arg]
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = Recording
        fields = [
            "instrument", "recording_type", "tags", "idea_stage",
            "location", "mood", "rating", "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput())
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput())

    def clean_username(self) -> str:
        username = self.cleaned_data["username"]
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self) -> dict[str, Any]:
        data = super().clean()
        p1 = data.get("password1")
        p2 = data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return data


class CommentForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={"rows": 3, "placeholder": "What to try next, what didn't work, ideas..."}
            )
        }
        labels = {"text": "Add a comment"}
