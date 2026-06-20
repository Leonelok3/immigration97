from django.conf import settings
from django.db import models
from django.utils import timezone


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    full_name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    linkedin_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)

    # Préférences
    preferred_location = models.CharField(max_length=160, blank=True)
    preferred_remote = models.BooleanField(default=False)
    preferred_contract = models.CharField(max_length=80, blank=True)  # CDI, CDD, Stage...
    preferred_salary = models.CharField(max_length=80, blank=True)    # "1200-1800€" etc.
    language = models.CharField(max_length=10, default="fr")          # fr/en

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"CandidateProfile({self.user})"


class CandidateDocuments(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_documents",
    )
    cv_file = models.FileField(upload_to="job_agent/cv/", blank=True, null=True)
    cover_letter_file = models.FileField(upload_to="job_agent/letters/", blank=True, null=True)

    # Texte (pour matching + génération)
    cv_text = models.TextField(blank=True)
    base_letter_text = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "updated_at"]),
        ]

    def __str__(self):
        return f"CandidateDocuments({self.user})"


class JobSearch(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_searches",
    )
    title = models.CharField(max_length=140)  # ex: "Développeur Python Junior"
    keywords = models.CharField(max_length=400, blank=True)  # ex: "django, api, postgres"
    location = models.CharField(max_length=160, blank=True)
    remote_ok = models.BooleanField(default=False)
    contract_type = models.CharField(max_length=80, blank=True)
    language = models.CharField(max_length=10, default="fr")

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.user})"


class JobLead(models.Model):
    STATUS_FOUND = "found"
    STATUS_TO_APPLY = "to_apply"
    STATUS_APPLIED = "applied"
    STATUS_FOLLOWUP = "followup"
    STATUS_REPLY = "reply"

    STATUS_CHOICES = [
        (STATUS_FOUND, "Trouvée"),
        (STATUS_TO_APPLY, "À postuler"),
        (STATUS_APPLIED, "Postulée"),
        (STATUS_FOLLOWUP, "Relance"),
        (STATUS_REPLY, "Réponse"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_leads",
    )
    search = models.ForeignKey(
        JobSearch,
        on_delete=models.SET_NULL,
        related_name="leads",
        null=True,
        blank=True,
    )

    url = models.URLField()
    source = models.CharField(max_length=60, blank=True)  # "Indeed", "LinkedIn", "Site entreprise", etc.

    title = models.CharField(max_length=220, blank=True)
    company = models.CharField(max_length=220, blank=True)
    location = models.CharField(max_length=220, blank=True)

    description_text = models.TextField(blank=True)

    match_score = models.PositiveIntegerField(default=0)  # 0..100
    match_summary = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_FOUND,
        db_index=True,
    )

    # ✅ RELANCE (Phase Follow-up)
    contact_email = models.EmailField(blank=True)  # email RH/recruteur
    applied_at = models.DateTimeField(null=True, blank=True)  # date de candidature
    followup_sent_at = models.DateTimeField(null=True, blank=True)  # dernière relance envoyée

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # ✅ Empêche doublons : un user ne peut pas ajouter deux fois la même URL
            models.UniqueConstraint(fields=["user", "url"], name="uniq_joblead_user_url"),
        ]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
            models.Index(fields=["user", "match_score"]),
            models.Index(fields=["user", "applied_at"]),
        ]

    def __str__(self):
        return f"{self.title or 'Offre'} - {self.company or ''}"


class ApplicationPack(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="application_packs",
    )
    lead = models.OneToOneField(
        JobLead,
        on_delete=models.CASCADE,
        related_name="pack",
    )

    generated_letter = models.TextField(blank=True)
    suggested_answers = models.JSONField(default=dict, blank=True)

    # ✅ Phase 5 (Email)
    email_subject = models.CharField(max_length=200, blank=True)
    generated_email = models.TextField(blank=True)

    tailored_cv_text = models.TextField(blank=True)
    ats_score = models.PositiveSmallIntegerField(default=0)
    matched_keywords = models.JSONField(default=list, blank=True)
    missing_keywords = models.JSONField(default=list, blank=True)
    coach_notes = models.TextField(blank=True)
    ai_status = models.CharField(max_length=30, blank=True)
    ai_generated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "updated_at"]),
        ]

    def __str__(self):
        return f"ApplicationPack({self.lead_id})"


class PublicJobOffer(models.Model):
    """
    Offres “publiques” que TOI (admin) ajoutes depuis Django admin.
    Les utilisateurs peuvent les importer dans leur espace.
    """
    source = models.CharField(max_length=60, blank=True)  # Indeed, Site entreprise, etc.
    url = models.URLField(max_length=600, unique=True)

    title = models.CharField(max_length=220)
    company = models.CharField(max_length=220, blank=True)
    location = models.CharField(max_length=220, blank=True)
    category = models.ForeignKey(
        "profiles.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="public_job_offers",
        help_text="Métier/catégorie cible pour recommander cette offre aux candidats.",
    )
    skills_keywords = models.CharField(
        max_length=300,
        blank=True,
        help_text="Mots-clés séparés par des virgules: Python, soudure, Excel...",
    )
    foreign_access_score = models.PositiveSmallIntegerField(
        default=0,
        help_text="Score 0-100 indiquant si l'offre semble accessible aux candidats étrangers.",
    )
    foreign_access_label = models.CharField(
        max_length=80,
        blank=True,
        help_text="Badge lisible: Accessible étranger, LMIA/EIMT, À vérifier...",
    )
    salary = models.CharField(max_length=180, blank=True)
    province = models.CharField(max_length=80, blank=True)
    application_deadline = models.CharField(max_length=80, blank=True)
    vacancies = models.CharField(max_length=80, blank=True)
    who_can_apply = models.TextField(blank=True)

    description_text = models.TextField(blank=True)

    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "created_at"]),
            models.Index(fields=["category", "is_active", "created_at"]),
            models.Index(fields=["foreign_access_score", "is_active", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.company}"


class AnswerTemplate(models.Model):
    """
    Réponses types gérées depuis l’admin (ex: Disponibilité, Salaire, Motivation).
    """
    title = models.CharField(max_length=120)
    language = models.CharField(max_length=10, default="fr")
    key = models.CharField(max_length=60)  # ex: "Disponibilité", "Salaire", "Motivation"
    content = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["language", "key", "is_active"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.key})"


class LetterTemplate(models.Model):
    """
    Modèles de lettres gérés depuis l’admin.
    Tu peux utiliser des variables: {title}, {company}, {location}, {name}
    """
    title = models.CharField(max_length=120)
    language = models.CharField(max_length=10, default="fr")
    content = models.TextField(help_text="Utilise {title}, {company}, {location}, {name}…")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["language", "is_active"]),
        ]

    def __str__(self):
        return self.title


class FollowUpTemplate(models.Model):
    """
    ✅ Template de relance géré depuis l'admin
    Variables: {name} {title} {company} {location}
    """
    title = models.CharField(max_length=120)
    language = models.CharField(max_length=10, default="fr")
    subject = models.CharField(max_length=200, help_text="Ex: Relance — {title} ({company})")
    content = models.TextField(help_text="Variables: {name} {title} {company} {location}")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["language", "is_active"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.language})"
