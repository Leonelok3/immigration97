# visaetude/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import UserProfile, UserChecklist, StudentProfile

# ============================================================
# Constantes pour la validation des fichiers
# ============================================================
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg", "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_UPLOAD_MB = 10

# ============================================================
# Formulaire Profil Utilisateur (Visa Études)
# ============================================================
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["pays_origine", "niveau_etude", "domaine_etude",
                  "budget_disponible", "telephone"]
        labels = {
            "pays_origine": _("Pays d’origine"),
            "niveau_etude": _("Niveau d’étude actuel"),
            "domaine_etude": _("Domaine d’étude / Filière"),
            "budget_disponible": _("Budget disponible (FCFA)"),
            "telephone": _("Téléphone"),
        }
        widgets = {
            "pays_origine": forms.Select(attrs={"class": "form-select"}),
            "niveau_etude": forms.Select(attrs={"class": "form-select"}),
            "domaine_etude": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Informatique"}),
            "budget_disponible": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "10000"}),
            "telephone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+237..."}),
        }

    def clean_budget_disponible(self):
        v = self.cleaned_data.get("budget_disponible")
        if v is not None and v < 0:
            raise ValidationError(_("Le budget ne peut pas être négatif."))
        return v

# ============================================================
# Formulaire Mise à jour Checklist
# ============================================================
class ChecklistUpdateForm(forms.ModelForm):
    class Meta:
        model = UserChecklist
        fields = ["statut", "fichier", "notes"]
        labels = {
            "statut": _("Statut"),
            "fichier": _("Fichier"),
            "notes":  _("Notes"),
        }
        widgets = {
            "statut": forms.Select(attrs={"class": "form-select"}),
            "fichier": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_fichier(self):
        f = self.cleaned_data.get("fichier")
        if not f:
            return f
        if f.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise ValidationError(_(f"Fichier trop volumineux (≤ {MAX_UPLOAD_MB} Mo)."))
        ctype = getattr(f, "content_type", None)
        if ctype and ctype not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(_("Type de fichier non pris en charge. PDF/JPG/PNG/DOCX uniquement."))
        ext = (f.name.rsplit(".", 1)[-1] or "").lower()
        if ctype is None and ext not in {"pdf", "jpg", "jpeg", "png", "docx"}:
            raise ValidationError(_("Extension non autorisée. PDF/JPG/PNG/DOCX uniquement."))
        return f

# ============================================================
# Formulaire Profil Étudiant (Diagnostic Visa Études)
# ============================================================
class StudentProfileForm(forms.ModelForm):
    education_level = forms.ChoiceField(
        label=_("Niveau d’études actuel"),
        required=False,
        choices=[
            ("", "Choisir un niveau"),
            ("secondaire", "Secondaire / Bac"),
            ("bts_dut", "BTS / DUT / Bac+2"),
            ("licence", "Licence / Bachelor"),
            ("master", "Master"),
            ("doctorat", "Doctorat"),
            ("autre", "Autre"),
        ],
    )
    budget_range = forms.ChoiceField(
        label=_("Budget estimatif (par an)"),
        required=False,
        choices=[
            ("", "Choisir un budget"),
            ("moins_3m", "Moins de 3 000 000 FCFA"),
            ("3m_6m", "3 000 000 - 6 000 000 FCFA"),
            ("6m_10m", "6 000 000 - 10 000 000 FCFA"),
            ("10m_plus", "Plus de 10 000 000 FCFA"),
        ],
    )
    language_level = forms.ChoiceField(
        label=_("Niveau de langue principal"),
        required=False,
        choices=[
            ("", "Choisir un niveau"),
            ("a1_a2", "A1 - A2"),
            ("b1", "B1"),
            ("b2", "B2"),
            ("c1", "C1"),
            ("c2", "C2"),
            ("ielts_tef", "Score IELTS / TEF / TCF disponible"),
        ],
    )

    class Meta:
        model = StudentProfile
        fields = [
            "country_of_origin",
            "education_level",
            "field_of_study",
            "study_goal",
            "target_year",
            "budget_range",
            "language_level",
        ]
        labels = {
            "country_of_origin": _("Pays d’origine"),
            "education_level": _("Niveau d’études actuel"),
            "field_of_study": _("Domaine d’études / spécialité"),
            "study_goal": _("Objectif académique"),
            "target_year": _("Année de départ souhaitée"),
            "budget_range": _("Budget estimatif (par an)"),
            "language_level": _("Niveau de langue principal"),
        }
        widgets = {
            "country_of_origin": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Cameroun, Sénégal, Côte d'Ivoire..."}),
            "field_of_study": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Informatique, santé, gestion, génie civil..."}),
            "study_goal": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Ex: Faire un Master au Canada puis demander un permis post-diplôme."}),
            "target_year": forms.NumberInput(attrs={"class": "form-control", "min": "2026", "placeholder": "Ex: 2027"}),
        }
