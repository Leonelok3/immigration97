from django import forms
from .models import CandidateProfile, CandidateDocuments, JobSearch, JobLead


class CandidateProfileForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = [
            "full_name", "phone", "city", "country",
            "linkedin_url", "portfolio_url",
            "preferred_location", "preferred_remote", "preferred_contract", "preferred_salary",
            "language",
        ]


from django import forms
from .models import CandidateProfile, CandidateDocuments, JobSearch, JobLead


class CandidateProfileForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = [
            "full_name", "phone", "city", "country",
            "linkedin_url", "portfolio_url",
            "preferred_location", "preferred_remote", "preferred_contract", "preferred_salary",
            "language",
        ]


class CandidateDocumentsForm(forms.ModelForm):
    # ✅ Nouveau: checkbox pour extraire automatiquement le texte du PDF
    auto_extract_cv = forms.BooleanField(
        required=False,
        initial=True,
        label="Extraire automatiquement le texte du CV (PDF)",
        help_text="Coche pour remplir automatiquement le champ 'Texte CV' après upload.",
    )

    class Meta:
        model = CandidateDocuments
        fields = ["cv_file", "cover_letter_file", "cv_text", "base_letter_text"]

        widgets = {
            "cv_file": forms.FileInput(attrs={"accept": ".pdf,application/pdf"}),
            "cover_letter_file": forms.FileInput(attrs={"accept": ".pdf,.doc,.docx,application/pdf"}),
            "cv_text": forms.Textarea(
                attrs={"rows": 16, "placeholder": "Texte CV extrait automatiquement depuis le PDF. Corrigez ici si besoin."}
            ),
            "base_letter_text": forms.Textarea(
                attrs={"rows": 10, "placeholder": "Ta lettre de motivation de base (optionnel)."}
            ),
        }


class JobSearchForm(forms.ModelForm):
    class Meta:
        model = JobSearch
        fields = ["title", "keywords", "location", "remote_ok", "contract_type", "language"]


class JobLeadAddForm(forms.ModelForm):
    class Meta:
        model = JobLead
        fields = ["search", "url", "source", "title", "company", "location", "description_text", "status"]
        widgets = {
            "description_text": forms.Textarea(
                attrs={"rows": 10, "placeholder": "Colle la description de l’offre ici (recommandé)."}
            ),
        }


class JobLeadBulkAddForm(forms.Form):
    payload = forms.CharField(
        label="Offres à importer",
        widget=forms.Textarea(
            attrs={
                "rows": 16,
                "placeholder": (
                    "Sépare chaque offre avec ---\n\n"
                    "URL: https://...\n"
                    "Titre: ...\n"
                    "Entreprise: ...\n"
                    "Lieu: ...\n"
                    "Source: ...\n"
                    "Description:\n"
                    "Texte...\n"
                    "---\n"
                    "URL: https://...\n"
                    "Description:\n"
                    "Texte...\n"
                ),
            }
        ),
        help_text="Sépare chaque offre avec --- (trois tirets).",
    )

    default_source = forms.CharField(
        label="Source par défaut (optionnel)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Indeed / Site entreprise / LinkedIn"}),
    )



class JobSearchForm(forms.ModelForm):
    class Meta:
        model = JobSearch
        fields = ["title", "keywords", "location", "remote_ok", "contract_type", "language"]

        widgets = {
            "keywords": forms.TextInput(
                attrs={"placeholder": "Ex: django, python, api, postgres, linux"}
            )
        }


class JobLeadAddForm(forms.ModelForm):
    class Meta:
        model = JobLead
        fields = ["search", "url", "source", "title", "company", "location", "description_text", "status"]
        widgets = {
            "url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "description_text": forms.Textarea(
                attrs={
                    "rows": 10,
                    "placeholder": "Colle la description de l’offre ici (recommandé).",
                }
            ),
        }


class JobLeadBulkAddForm(forms.Form):
    """
    Ajout en masse pour postuler vite :
    - l'utilisateur colle plusieurs offres (URL + description)
    - le système importera + scorera automatiquement

    Format attendu (séparer les offres avec '---'):

    URL: https://...
    Titre: Développeur Python
    Entreprise: ACME
    Lieu: Paris
    Source: Indeed
    Description:
    ...texte...
    ---
    URL: https://...
    Description:
    ...texte...
    """

    payload = forms.CharField(
        label="Offres à importer",
        widget=forms.Textarea(
            attrs={
                "rows": 16,
                "placeholder": (
                    "Colle plusieurs offres, séparées par ---\n\n"
                    "URL: https://...\n"
                    "Titre: ... (optionnel)\n"
                    "Entreprise: ... (optionnel)\n"
                    "Lieu: ... (optionnel)\n"
                    "Source: ... (optionnel)\n"
                    "Description:\n"
                    "Texte de l'offre...\n"
                    "---\n"
                    "URL: https://...\n"
                    "Description:\n"
                    "Texte de l'offre...\n"
                ),
            }
        ),
        help_text="Sépare chaque offre avec --- (trois tirets).",
    )

    default_source = forms.CharField(
        label="Source par défaut (optionnel)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Indeed / Site entreprise / LinkedIn"}),
        help_text="Si une offre n’a pas 'Source:' dans le bloc, on utilisera cette valeur.",
    )


# ---- Optionnel (si tu ajoutes la logique “filtre rapide” sur la liste des offres)
class JobLeadFilterForm(forms.Form):
    status = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=[("", "Tous")] + list(JobLead.STATUS_CHOICES),
    )
    min_score = forms.IntegerField(
        label="Score minimum",
        required=False,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={"placeholder": "ex: 60"}),
    )
    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Titre / entreprise / lieu"}),
    )
