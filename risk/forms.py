from django import forms

from .models import Assessment


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ["title", "site", "rule_percent"]


class TaskUpdateForm(forms.Form):
    progress = forms.IntegerField(min_value=0, max_value=100, required=False)
    text = forms.CharField(required=False, widget=forms.Textarea)
    photo = forms.ImageField(required=False)
