from django import forms

from outreach.models import JobVisaEligibilityAssessment, RecruiterContact


class JobVisaEligibilityForm(forms.ModelForm):
    preferred_countries = forms.CharField(
        label="Pays préférés",
        help_text="Exemples: CA,NZ,AU,EU ou CA,GB,DE",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "CA,NZ,AU,EU"}),
    )

    class Meta:
        model = JobVisaEligibilityAssessment
        fields = [
            "age",
            "country",
            "city",
            "profession",
            "sector",
            "years_experience",
            "education_level",
            "certificates",
            "french_level",
            "english_level",
            "has_passport",
            "has_cv",
            "budget",
            "preferred_countries",
        ]
        widgets = {
            "certificates": forms.Textarea(attrs={"rows": 3, "placeholder": "Ex: Bac, BTS, permis, certificat soudure, attestation employeur..."}),
            "country": forms.TextInput(attrs={"placeholder": "Cameroun"}),
            "city": forms.TextInput(attrs={"placeholder": "Douala, Yaoundé..."}),
            "profession": forms.TextInput(attrs={"placeholder": "Ex: ouvrier agricole, aide-soignant, soudeur..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sector"].choices = RecruiterContact.SECTOR_CHOICES
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} jv-field".strip()
