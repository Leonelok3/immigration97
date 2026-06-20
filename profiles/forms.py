from django import forms
from .models import Profile, PortfolioItem, Skill


MAX_PORTFOLIO_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_PORTFOLIO_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "category",
            "headline",
            "location",
            "bio",
            "linkedin_url",
            "avatar",
            "is_public",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "profile-input"}),
            "headline": forms.TextInput(attrs={"class": "profile-input"}),
            "location": forms.TextInput(attrs={"class": "profile-input"}),
            "bio": forms.Textarea(attrs={"class": "profile-input"}),
            "linkedin_url": forms.URLInput(attrs={"class": "profile-input"}),
            "is_public": forms.CheckboxInput(attrs={"class": "profile-check"}),
        }


class PortfolioItemForm(forms.ModelForm):
    class Meta:
        model = PortfolioItem
        fields = ['title', 'item_type', 'file', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'item_type': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if not file:
            return file

        if file.size > MAX_PORTFOLIO_FILE_SIZE:
            raise forms.ValidationError("Fichier trop lourd : maximum 10 Mo.")

        content_type = getattr(file, "content_type", "")
        if content_type not in ALLOWED_PORTFOLIO_CONTENT_TYPES:
            raise forms.ValidationError("Format accepté : PDF, JPG, PNG ou WebP.")

        return file


class SkillForm(forms.Form):
    skill_name = forms.CharField(
        max_length=80,
        label="Compétence",
        widget=forms.TextInput(attrs={
            "placeholder": "Ex: Python, Menuiserie, Excel, Soudure…",
            "list": "skill-suggestions",
            "autocomplete": "off",
        }),
    )
    level = forms.IntegerField(
        min_value=1, max_value=5, initial=3,
        label="Niveau",
        widget=forms.NumberInput(attrs={"min": "1", "max": "5"}),
    )
    years = forms.IntegerField(
        min_value=0, max_value=40, initial=0, required=False,
        label="Années d'expérience",
        widget=forms.NumberInput(attrs={"min": "0", "max": "40"}),
    )


class ContactCandidateForm(forms.Form):
    recruiter_name = forms.CharField(label="Votre nom", widget=forms.TextInput(attrs={'class': 'form-control'}))
    recruiter_email = forms.EmailField(label="Votre email", widget=forms.EmailInput(attrs={'class': 'form-control'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), label="Message")


class AvatarUploadForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar"]

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            if avatar.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Image trop lourde (max 2 Mo).")
            if avatar.content_type not in ["image/jpeg", "image/png"]:
                raise forms.ValidationError("Format non supporté (JPG / PNG uniquement).")
        return avatar
