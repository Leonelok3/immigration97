from django import forms
from .models import PRProfile


class PREligibilityForm(forms.ModelForm):
    class Meta:
        model = PRProfile
        fields = [
            "country",
            "age",
            "years_experience",
            "education_level",

            "french_exam",
            "french_level",
            "french_co",
            "french_ce",
            "french_eo",
            "french_ee",

            "english_exam",
            "english_level",
            "english_co",
            "english_ce",
            "english_eo",
            "english_ee",

            "profession_title",
            "noc_code",
            "anzsco_code",
            "has_family_in_country",
            "has_job_offer",
            "notes",
        ]
        labels = {
            "country": "Pays ciblé",
            "age": "Âge",
            "years_experience": "Années d’expérience (temps plein)",
            "education_level": "Niveau d’études",

            "french_exam": "Test de français",
            "french_level": "Niveau global de français",
            "french_co": "Français – CO (compréhension orale)",
            "french_ce": "Français – CE (compréhension écrite)",
            "french_eo": "Français – EO (expression orale)",
            "french_ee": "Français – EE (expression écrite)",

            "english_exam": "Test d’anglais",
            "english_level": "Niveau global d’anglais",
            "english_co": "Anglais – Listening (CO)",
            "english_ce": "Anglais – Reading (CE)",
            "english_eo": "Anglais – Speaking (EO)",
            "english_ee": "Anglais – Writing (EE)",

            "profession_title": "Profession principale",
            "noc_code": "Code NOC / TEER (Canada)",
            "anzsco_code": "Code ANZSCO (Australie)",
            "has_family_in_country": "Famille sur place",
            "has_job_offer": "Offre d’emploi valide",
            "notes": "Infos complémentaires",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Le diagnostic actuel cible le Canada et le champ n'est pas affiché
        # dans le template. On garde donc une valeur par défaut côté formulaire.
        self.fields["country"].required = False
        self.fields["country"].initial = "CA"

        # placeholders pro
        placeholders = {
            "age": "Ex : 29",
            "years_experience": "Ex : 3 (années à temps plein)",
            "french_co": "Ex : 310/360, CLB 7, B2…",
            "french_ce": "Ex : 280/300, CLB 8, B2…",
            "french_eo": "Ex : B2 fort, CLB 7…",
            "french_ee": "Ex : B2, CLB 7…",

            "english_co": "Ex : 6.5, 7.0, CLB 8…",
            "english_ce": "Ex : 7.0, 7.5, CLB 9…",
            "english_eo": "Ex : 6.5, 7.0…",
            "english_ee": "Ex : 6.0, 6.5…",

            "profession_title": "Ex : Enseignant, Ingénieur logiciel, Infirmier…",
            "noc_code": "Ex : 41220, 21231…",
            "anzsco_code": "Ex : 241111, 261313…",
            "notes": "Ajoute ici tout contexte utile (projet, situation familiale, contraintes…).",
        }

        # classes de base pour le thème dark immigration97
        input_class = (
            "w-full px-4 py-2 rounded-xl bg-[#0b1a24] text-white border "
            "border-[#11303a] focus:border-emerald-500 focus:ring-emerald-500 "
            "placeholder-gray-500"
        )

        select_class = (
            "w-full px-4 py-2 rounded-xl bg-[#0b1a24] text-white border "
            "border-[#11303a] focus:border-emerald-500 focus:ring-emerald-500"
        )

        checkbox_class = (
            "h-4 w-4 rounded bg-[#0b1a24] text-emerald-500 border-[#11303a] "
            "focus:ring-emerald-600"
        )

        for name, field in self.fields.items():
            widget = field.widget
            widget_name = widget.__class__.__name__

            # placeholders
            if name in placeholders:
                widget.attrs["placeholder"] = placeholders[name]

            # récupérer les classes existantes
            existing_classes = widget.attrs.get("class", "")

            if widget_name in ["TextInput", "NumberInput"]:
                widget.attrs["class"] = (existing_classes + " " + input_class).strip()

            elif widget_name == "Textarea":
                widget.attrs["class"] = (existing_classes + " " + input_class + " min-h-[80px]").strip()

            elif widget_name == "Select":
                widget.attrs["class"] = (existing_classes + " " + select_class).strip()

            elif widget_name == "CheckboxInput":
                widget.attrs["class"] = (existing_classes + " " + checkbox_class).strip()
