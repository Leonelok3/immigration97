from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class RecruiterContact(models.Model):
    SECTOR_CHOICES = [
        ("agriculture", "Agriculture / Agroalimentaire"),
        ("construction", "Construction / BTP"),
        ("tech", "Technologie / IT"),
        ("sante", "Santé / Médical"),
        ("logistique", "Transport / Logistique"),
        ("hotellerie", "Hôtellerie / Restauration"),
        ("education", "Éducation / Formation"),
        ("finance", "Finance / Comptabilité"),
        ("industrie", "Industrie / Manufacture"),
        ("commerce", "Commerce / Vente"),
        ("services", "Services aux entreprises"),
        ("autre", "Autre"),
    ]

    COUNTRY_CHOICES = [
        ("CA", "Canada"),
        ("NZ", "Nouvelle-Zélande"),
        ("FR", "France"),
        ("DE", "Allemagne"),
        ("BE", "Belgique"),
        ("CH", "Suisse"),
        ("AU", "Australie"),
        ("GB", "Royaume-Uni"),
        ("US", "États-Unis"),
        ("MA", "Maroc"),
        ("SN", "Sénégal"),
        ("CI", "Côte d'Ivoire"),
        ("OTHER", "Autre"),
    ]

    STATUS_CHOICES = [
        ("new", "Nouveau"),
        ("contacted", "Contacté"),
        ("opened", "Email ouvert"),
        ("replied", "A répondu"),
        ("registered", "Inscrit sur la plateforme"),
        ("not_interested", "Pas intéressé"),
        ("bounce", "Bounce / Email invalide"),
    ]

    SOURCE_CHOICES = [
        ("manual", "Ajout manuel"),
        ("csv_import", "Import CSV/Excel"),
        ("ai_search", "Agent IA"),
        ("web", "Recherche web"),
    ]

    # Identité
    company_name = models.CharField("Entreprise", max_length=200)
    contact_name = models.CharField("Nom du contact", max_length=150, blank=True)
    job_title = models.CharField("Poste (ex: DRH, Manager RH)", max_length=120, blank=True)
    email = models.EmailField("Email", unique=True)
    phone = models.CharField("Téléphone", max_length=40, blank=True)
    website = models.URLField("Site web", max_length=300, blank=True)

    # Catégorie
    sector = models.CharField("Secteur", max_length=30, choices=SECTOR_CHOICES, default="autre", db_index=True)
    country = models.CharField("Pays", max_length=10, choices=COUNTRY_CHOICES, default="CA", db_index=True)
    city = models.CharField("Ville", max_length=120, blank=True)

    # Workflow
    status = models.CharField("Statut", max_length=20, choices=STATUS_CHOICES, default="new", db_index=True)
    source = models.CharField("Source", max_length=20, choices=SOURCE_CHOICES, default="manual")
    tags = models.CharField("Tags", max_length=300, blank=True, help_text="Mots-clés séparés par des virgules")
    notes = models.TextField("Notes internes", blank=True)

    # Suivi
    last_contacted_at = models.DateTimeField("Dernier contact", null=True, blank=True)
    last_replied_at = models.DateTimeField("Dernière réponse", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contact Recruteur"
        verbose_name_plural = "Contacts Recruteurs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company_name} — {self.email}"


class ScrapedEmployerLead(models.Model):
    STATUS_CHOICES = [
        ("new", "Nouveau"),
        ("reviewed", "Vérifié"),
        ("imported", "Importé"),
        ("rejected", "Rejeté"),
    ]

    COUNTRY_CHOICES = [
        ("CA", "Canada"),
        ("NZ", "Nouvelle-Zélande"),
        ("AU", "Australie"),
        ("EU", "Europe"),
        ("FR", "France"),
        ("DE", "Allemagne"),
        ("BE", "Belgique"),
        ("CH", "Suisse"),
        ("GB", "Royaume-Uni"),
        ("IE", "Irlande"),
        ("NL", "Pays-Bas"),
        ("IT", "Italie"),
        ("ES", "Espagne"),
        ("PT", "Portugal"),
        ("OTHER", "Autre"),
    ]

    title = models.CharField("Titre / poste", max_length=240)
    company_name = models.CharField("Employeur", max_length=220, blank=True)
    country = models.CharField("Pays cible", max_length=10, choices=COUNTRY_CHOICES, db_index=True)
    sector = models.CharField("Secteur", max_length=30, choices=RecruiterContact.SECTOR_CHOICES, default="autre", db_index=True)
    location = models.CharField("Localisation", max_length=180, blank=True)

    job_url = models.URLField("URL offre / preuve", max_length=600, unique=True)
    source_url = models.URLField("URL source", max_length=600, blank=True)
    website = models.URLField("Site employeur", max_length=400, blank=True)
    contact_email = models.EmailField("Email détecté", blank=True)

    visa_signal = models.CharField("Signal visa", max_length=180, blank=True)
    evidence_text = models.TextField("Extrait de preuve", blank=True)
    confidence_score = models.PositiveSmallIntegerField("Score confiance", default=0)
    verification_score = models.PositiveSmallIntegerField("Score vérification", default=0)
    verification_decision = models.CharField("Décision vérification", max_length=20, blank=True, db_index=True)
    verification_notes = models.TextField("Notes vérification", blank=True)
    verification_signals = models.JSONField("Signaux vérification", default=list, blank=True)
    status = models.CharField("Statut", max_length=20, choices=STATUS_CHOICES, default="new", db_index=True)
    raw_data = models.JSONField("Données brutes", default=dict, blank=True)

    first_seen_at = models.DateTimeField("Première détection", auto_now_add=True)
    last_seen_at = models.DateTimeField("Dernière détection", auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lead employeur scrapé"
        verbose_name_plural = "Leads employeurs scrapés"
        ordering = ["-last_seen_at", "-confidence_score"]
        indexes = [
            models.Index(fields=["country", "sector", "status"], name="outreach_scraped_country_idx"),
            models.Index(fields=["confidence_score", "last_seen_at"], name="outreach_scraped_score_idx"),
        ]

    def __str__(self):
        company = self.company_name or "Employeur à vérifier"
        return f"{company} — {self.title}"


class ScamAssessment(models.Model):
    RISK_CHOICES = [
        ("low", "Faible"),
        ("medium", "Moyen"),
        ("high", "Élevé"),
    ]

    lead = models.OneToOneField(
        ScrapedEmployerLead,
        on_delete=models.CASCADE,
        related_name="scam_assessment",
        verbose_name="Lead employeur",
    )
    risk_score = models.PositiveSmallIntegerField("Score risque", default=0, db_index=True)
    risk_level = models.CharField("Niveau risque", max_length=20, choices=RISK_CHOICES, default="medium", db_index=True)
    flags = models.JSONField("Alertes détectées", default=list, blank=True)
    recommendation = models.TextField("Recommandation", blank=True)
    assessed_at = models.DateTimeField("Date d'analyse", auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Analyse anti-arnaque"
        verbose_name_plural = "Analyses anti-arnaque"
        ordering = ["-assessed_at", "-risk_score"]
        indexes = [
            models.Index(fields=["risk_level", "risk_score"], name="outreach_scam_risk_idx"),
        ]

    def __str__(self):
        return f"{self.lead} — risque {self.risk_level} ({self.risk_score})"


class JobVisaEligibilityAssessment(models.Model):
    EDUCATION_CHOICES = [
        ("none", "Aucun diplôme"),
        ("secondary", "Secondaire / Bac"),
        ("vocational", "Formation professionnelle / CAP / BTS"),
        ("bachelor", "Licence / Bachelor"),
        ("master", "Master"),
        ("phd", "Doctorat"),
    ]

    LANGUAGE_CHOICES = [
        ("none", "Aucun / débutant"),
        ("a1", "A1"),
        ("a2", "A2"),
        ("b1", "B1"),
        ("b2", "B2"),
        ("c1", "C1"),
        ("c2", "C2"),
    ]

    BUDGET_CHOICES = [
        ("low", "Moins de 300 000 FCFA"),
        ("medium", "300 000 à 1 500 000 FCFA"),
        ("good", "1 500 000 à 4 000 000 FCFA"),
        ("strong", "Plus de 4 000 000 FCFA"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="job_visa_assessments")
    age = models.PositiveSmallIntegerField("Âge")
    country = models.CharField("Pays de résidence", max_length=120)
    city = models.CharField("Ville", max_length=120, blank=True)
    profession = models.CharField("Métier principal", max_length=160)
    sector = models.CharField("Secteur", max_length=30, choices=RecruiterContact.SECTOR_CHOICES, default="autre")
    years_experience = models.PositiveSmallIntegerField("Années d'expérience", default=0)
    education_level = models.CharField("Niveau d'études", max_length=20, choices=EDUCATION_CHOICES, default="secondary")
    certificates = models.TextField("Diplômes / certificats", blank=True)
    french_level = models.CharField("Niveau français", max_length=10, choices=LANGUAGE_CHOICES, default="b1")
    english_level = models.CharField("Niveau anglais", max_length=10, choices=LANGUAGE_CHOICES, default="none")
    has_passport = models.BooleanField("Passeport disponible", default=False)
    has_cv = models.BooleanField("CV disponible", default=False)
    budget = models.CharField("Budget approximatif", max_length=20, choices=BUDGET_CHOICES, default="medium")
    preferred_countries = models.CharField(
        "Pays préférés",
        max_length=120,
        default="CA,NZ,AU,EU",
        help_text="Codes séparés par virgule: CA,NZ,AU,GB,DE,BE,FR,EU",
    )

    readiness_score = models.PositiveSmallIntegerField("Score préparation", default=0)
    recommended_countries = models.JSONField("Pays recommandés", default=list, blank=True)
    accessible_jobs = models.JSONField("Métiers accessibles", default=list, blank=True)
    missing_documents = models.JSONField("Documents manquants", default=list, blank=True)
    action_plan = models.JSONField("Plan d'action", default=list, blank=True)
    result_summary = models.TextField("Résumé résultat", blank=True)
    raw_result = models.JSONField("Résultat complet", default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Éligibilité emploi + visa"
        verbose_name_plural = "Éligibilités emploi + visa"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="outreach_jobvisa_user_idx"),
            models.Index(fields=["sector", "readiness_score"], name="outreach_jobvisa_sector_idx"),
        ]

    def __str__(self):
        return f"{self.user} — {self.profession} ({self.readiness_score}/100)"


class OutreachTemplate(models.Model):
    LANG_CHOICES = [("fr", "Français"), ("en", "Anglais")]

    name = models.CharField("Nom du template", max_length=150)
    language = models.CharField("Langue", max_length=5, choices=LANG_CHOICES, default="fr")
    subject = models.CharField(
        "Objet de l'email", max_length=200,
        help_text="Variables: {company_name}, {contact_name}, {sector_label}, {country_label}"
    )
    body_html = models.TextField(
        "Corps HTML",
        help_text="Variables: {company_name}, {contact_name}, {sector_label}, {country_label}"
    )
    body_text = models.TextField(
        "Corps texte brut",
        help_text="Version texte (fallback). Mêmes variables."
    )
    is_active = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template Email"
        verbose_name_plural = "Templates Email"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_language_display()}] {self.name}"


class OutreachCampaign(models.Model):
    STATUS_CHOICES = [
        ("draft", "Brouillon"),
        ("sending", "En cours d'envoi"),
        ("sent", "Envoyée"),
        ("paused", "En pause"),
    ]

    name = models.CharField("Nom de la campagne", max_length=200)
    template = models.ForeignKey(
        OutreachTemplate, on_delete=models.PROTECT,
        verbose_name="Template", related_name="campaigns"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Créé par"
    )

    filter_sectors = models.CharField(
        "Secteurs ciblés", max_length=500, blank=True,
        help_text="Vide = tous. Sinon: agriculture,tech,sante"
    )
    filter_countries = models.CharField(
        "Pays ciblés", max_length=200, blank=True,
        help_text="Vide = tous. Sinon: CA,FR,DE"
    )
    filter_status = models.CharField(
        "Statut contacts ciblés", max_length=200, blank=True,
        help_text="Défaut: new,contacted. Vide = tous (hors bounce)."
    )

    total_recipients = models.PositiveIntegerField("Total destinataires", default=0)
    sent_count = models.PositiveIntegerField("Envoyés", default=0)
    opened_count = models.PositiveIntegerField("Ouvertures", default=0)
    replied_count = models.PositiveIntegerField("Réponses", default=0)

    status = models.CharField("Statut", max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField("Date d'envoi", null=True, blank=True)

    class Meta:
        verbose_name = "Campagne Outreach"
        verbose_name_plural = "Campagnes Outreach"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def get_filter_sectors_list(self):
        return [s.strip() for s in self.filter_sectors.split(",") if s.strip()] if self.filter_sectors else []

    def get_filter_countries_list(self):
        return [c.strip() for c in self.filter_countries.split(",") if c.strip()] if self.filter_countries else []

    def get_filter_status_list(self):
        if not self.filter_status:
            return ["new", "contacted"]
        return [s.strip() for s in self.filter_status.split(",") if s.strip()]


class OutreachLog(models.Model):
    campaign = models.ForeignKey(OutreachCampaign, on_delete=models.CASCADE, related_name="logs")
    recruiter = models.ForeignKey(RecruiterContact, on_delete=models.SET_NULL, null=True, related_name="outreach_logs")
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    opened = models.BooleanField(default=False)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked = models.BooleanField(default=False)
    bounced = models.BooleanField(default=False)
    error = models.CharField(max_length=400, blank=True)

    class Meta:
        verbose_name = "Log Envoi"
        verbose_name_plural = "Logs Envois"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.campaign.name} → {self.recruiter or '?'}"
