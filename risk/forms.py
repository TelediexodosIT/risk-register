from django import forms

from .models import Assessment, Hazard


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ["title", "site", "rule_percent"]


class HazardForm(forms.ModelForm):
    """Validates the main hazard fields. Controls and new measures are handled in the view."""

    class Meta:
        model = Hazard
        fields = [
            "name", "category", "affects_operator", "affects_employees", "affects_third_parties",
            "consequences", "inherent_likelihood", "inherent_consequence",
            "residual_likelihood", "residual_consequence",
        ]


class TaskUpdateForm(forms.Form):
    progress = forms.IntegerField(min_value=0, max_value=100, required=False)
    text = forms.CharField(required=False, widget=forms.Textarea)
    photo = forms.ImageField(required=False)
