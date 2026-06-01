from django import forms

from .models import Comment, Instrument, Recording, Tag


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            if not data:
                raise forms.ValidationError(self.error_messages["required"], code="required")
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


class RecordingBatchUploadForm(forms.Form):
    files = MultipleFileField(
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
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))


class RecordingEditForm(forms.ModelForm):
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


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={"rows": 3, "placeholder": "What to try next, what didn't work, ideas..."}
            )
        }
        labels = {"text": "Add a comment"}
