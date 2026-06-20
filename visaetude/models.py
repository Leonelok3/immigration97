from django.conf import settings
from django.db import models
from django.contrib.auth.models import User


# ==================================================
# PROFIL UTILISATEUR — VISA ÉTUDES
# ==================================================
class UserProfile(models.Model):
    STUDY_LEVELS = [
        ("licence", "Licence"),
        ("master", "Master"),
        ("doctorat", "Doctorat"),
    ]

    COUNTRIES = [
        ("cameroun", "Cameroun"),
        ("senegal", "Sénégal"),
        ("cote_ivoire", "Côte d'Ivoire"),
        ("autre", "Autre"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="visaetude_profile"
    )

    pays_origine = models.CharField(max_length=50, choices=COUNTRIES)
    niveau_etude = models.CharField(max_length=20, choices=STUDY_LEVELS)
    domaine_etude = models.CharField(max_length=100)
    budget_disponible = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    telephone = models.CharField(max_length=20, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profil Visa Études – {self.user.username}"


# ==================================================
# PAYS VISA ÉTUDES
# ==================================================
class VisaCountry(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    short_label = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ==================================================
# RESSOURCES (VIDÉOS / PDF / CAPTURES)
# ==================================================
class VisaResource(models.Model):
    CATEGORY_CHOICES = [
        ("admission", "Admission"),
        ("visa", "Visa étudiant"),
        ("bourse", "Bourses"),
        ("rdv", "Rendez-vous"),
        ("divers", "Divers"),
    ]

    TYPE_CHOICES = [
        ("video", "Vidéo"),
        ("pdf", "PDF"),
        ("capture", "Capture"),
    ]

    country = models.ForeignKey(
        VisaCountry,
        on_delete=models.CASCADE,
        related_name="resources"
    )

    title = models.CharField(max_length=200)
    step_label = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    resource_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="video")
    url = models.URLField()
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["country", "order"]

    def __str__(self):
        return f"{self.country.name} – {self.title}"


# ==================================================
# UNIVERSITÉS
# ==================================================
class University(models.Model):
    name = models.CharField(max_length=255)
    country = models.ForeignKey(
        VisaCountry,
        on_delete=models.CASCADE,
        related_name="universities"
    )
    admission_link = models.URLField(blank=True, null=True)
    advice = models.TextField(blank=True, null=True)
    ranking = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.name


# ==================================================
# CONSEILS PAR PAYS
# ==================================================
class CountryAdvice(models.Model):
    country = models.ForeignKey(
        VisaCountry,
        on_delete=models.CASCADE,
        related_name="advices"
    )
    advice_title = models.CharField(max_length=255)
    advice_content = models.TextField()

    def __str__(self):
        return f"{self.country.name} – {self.advice_title}"


# ==================================================
# BOURSES
# ==================================================
class Scholarship(models.Model):
    country = models.ForeignKey(
        VisaCountry,
        on_delete=models.CASCADE,
        related_name="scholarships"
    )
    scholarship_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    description = models.TextField()
    application_link = models.URLField()

    def __str__(self):
        return self.scholarship_name


class PublicScholarshipOffer(models.Model):
    FUNDING_CHOICES = [
        ("full", "Bourse complète"),
        ("partial", "Bourse partielle"),
        ("tuition", "Frais de scolarité"),
        ("stipend", "Allocation"),
        ("unknown", "À vérifier"),
    ]

    LEVEL_CHOICES = [
        ("licence", "Licence"),
        ("master", "Master"),
        ("doctorat", "Doctorat"),
        ("postdoc", "Postdoctorat"),
        ("short", "Formation courte"),
        ("all", "Tous niveaux"),
        ("unknown", "À vérifier"),
    ]

    source = models.CharField(max_length=80, blank=True)
    url = models.URLField(max_length=700, unique=True)
    title = models.CharField(max_length=260)
    organization = models.CharField(max_length=220, blank=True)
    country = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    study_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="unknown")
    funding_type = models.CharField(max_length=20, choices=FUNDING_CHOICES, default="unknown")
    amount = models.CharField(max_length=180, blank=True)
    eligible_countries = models.CharField(max_length=260, blank=True)
    deadline = models.CharField(max_length=100, blank=True)
    requirements = models.TextField(blank=True)
    description_text = models.TextField(blank=True)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    verification_label = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-confidence_score", "-created_at"]
        indexes = [
            models.Index(fields=["is_active", "created_at"]),
            models.Index(fields=["country", "is_active", "created_at"]),
            models.Index(fields=["study_level", "is_active", "created_at"]),
            models.Index(fields=["funding_type", "is_active", "created_at"]),
            models.Index(fields=["confidence_score", "is_active", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.organization or self.country}"


# ==================================================
# CHECKLIST UTILISATEUR (DOCUMENTS VISA)
# ==================================================
class UserChecklist(models.Model):
    STATUS_CHOICES = [
        ("non_commence", "Non commencé"),
        ("en_cours", "En cours"),
        ("complete", "Complété"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="visaetude_checklists"
    )

    country = models.ForeignKey(
        VisaCountry,
        on_delete=models.CASCADE,
        related_name="checklists"
    )

    title = models.CharField(max_length=200)
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default="non_commence")
    fichier = models.FileField(upload_to="visaetude/documents/", null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} – {self.title}"


# ==================================================
# PROGRESSION GLOBALE — VISA ÉTUDES (UNIQUE)
# ==================================================
class VisaProgress(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="visa_progress"
    )

    step_1_profile = models.BooleanField(default=False)
    step_2_country = models.BooleanField(default=False)
    step_3_checklist = models.BooleanField(default=False)
    step_4_documents = models.BooleanField(default=False)
    step_5_coach = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def completed_steps(self):
        return sum([
            self.step_1_profile,
            self.step_2_country,
            self.step_3_checklist,
            self.step_4_documents,
            self.step_5_coach,
        ])

    @property
    def current_stage(self):
        return min(self.completed_steps + 1, 5)

    def __str__(self):
        return f"Progress Visa Études – {self.user}"


# ==================================================
# PROGRESSION UTILISATEUR — POUR LES ÉTAPES DANS LES VUES
# (Aligne avec ce que tes vues utilisent: step_1_profile, step_2_country, step_5_coach)
# ==================================================
class UserProgress(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_progress"
    )
    step_1_profile = models.BooleanField(default=False)
    step_2_country = models.BooleanField(default=False)
    step_5_coach = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"UserProgress – {self.user}"


# ==================================================
# PROFIL ÉTUDIANT — UNIFIÉ
# ==================================================
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")

    school = models.CharField(max_length=255, blank=True, null=True)
    program = models.CharField(max_length=255, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)

    field_of_study = models.CharField(max_length=200, blank=True, null=True)
    country_of_origin = models.CharField(max_length=100, blank=True, null=True)
    target_year = models.IntegerField(blank=True, null=True)
    education_level = models.CharField(max_length=100, blank=True, null=True)
    language_level = models.CharField(max_length=100, blank=True, null=True)
    study_goal = models.TextField(blank=True, null=True)
    budget_range = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.program or 'Profil étudiant'}"
