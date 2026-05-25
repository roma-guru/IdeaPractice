from django import forms

from .models import Instrument, Recording, Tag


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class RecordingBatchUploadForm(forms.Form):
    files = forms.FileField(
        widget=MultipleFileInput(),
        help_text="Select one or more recordings.",
    )
    instrument = forms.ModelChoiceField(queryset=Instrument.objects.all(), required=False)
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    idea_stage = forms.ChoiceField(choices=Recording.IdeaStage.choices, initial=Recording.IdeaStage.RAW)
    location = forms.CharField(max_length=200, required=False)
    mood = forms.CharField(max_length=120, required=False)
    rating = forms.IntegerField(min_value=0, max_value=10, required=False)
    is_practice = forms.BooleanField(required=False, initial=True)
    is_idea = forms.BooleanField(required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
