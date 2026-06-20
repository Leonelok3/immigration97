from django.db import models
from django.conf import settings


class HomeSlide(models.Model):
    THEME_CHOICES = [
        ("gold", "Or - Immigration97"),
        ("blue", "Bleu - Études"),
        ("green", "Vert - Résidence"),
        ("purple", "Violet - IA"),
        ("orange", "Orange - Ressources"),
    ]

    kicker = models.CharField("Petit label", max_length=80)
    title_before = models.CharField("Titre principal", max_length=140)
    title_accent = models.CharField("Titre accentué", max_length=90)
    subtitle = models.TextField("Description courte")
    primary_label = models.CharField("Bouton principal", max_length=60)
    primary_url = models.CharField("Lien bouton principal", max_length=220)
    secondary_label = models.CharField("Bouton secondaire", max_length=60, blank=True)
    secondary_url = models.CharField("Lien bouton secondaire", max_length=220, blank=True)
    background_image = models.ImageField(
        "Image de fond",
        upload_to="home/slides/",
        blank=True,
        null=True,
        help_text="Format recommandé : 1920 x 900 px, WebP ou JPG, moins de 350 Ko.",
    )
    theme = models.CharField("Style visuel", max_length=20, choices=THEME_CHOICES, default="gold")
    order = models.PositiveSmallIntegerField("Ordre", default=1, db_index=True)
    is_active = models.BooleanField("Actif", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Slide accueil"
        verbose_name_plural = "Slides accueil"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.order}. {self.kicker} - {self.title_before}"

    @property
    def title_before_lines(self):
        return [line.strip() for line in self.title_before.split("|") if line.strip()]


class ConsultationRequest(models.Model):
    TYPE_CHOICES = [
        ("visa_etude", "Visa Etudes"),
        ("visa_travail", "Visa Travail"),
        ("residence_permanente", "Résidence Permanente"),
        ("langue", "Préparation Test de Langue (TCF/TEF/DELF/DALF)"),
        ("allemand", "Cours d'Allemand"),
        ("cv", "Création / Optimisation CV"),
        ("profil", "Profil Candidat & Mise en Relation"),
        ("job_search", "Recherche d'Emploi à l'International"),
        ("autre", "Autre / Non listé"),
    ]

    STATUS_CHOICES = [
        ("new", "Nouvelle"),
        ("contacted", "Contacté(e)"),
        ("in_progress", "En cours de traitement"),
        ("completed", "Traité(e)"),
        ("cancelled", "Annulé(e)"),
    ]

    BUDGET_CHOICES = [
        ("less_50", "Moins de 50 €"),
        ("50_100", "50 – 100 €"),
        ("100_200", "100 – 200 €"),
        ("200_plus", "200 € et plus"),
        ("to_discuss", "À discuter"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="consultation_requests",
        verbose_name="Compte utilisateur"
    )

    full_name = models.CharField(max_length=150, verbose_name="Nom complet")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone / WhatsApp")
    country = models.CharField(max_length=80, blank=True, verbose_name="Pays de résidence actuel")

    consultation_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        verbose_name="Type de consultation"
    )

    destination_country = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Pays de destination visé"
    )

    message = models.TextField(
        verbose_name="Décrivez votre situation et vos besoins"
    )

    budget = models.CharField(
        max_length=20,
        choices=BUDGET_CHOICES,
        default="to_discuss",
        verbose_name="Budget indicatif"
    )

    preferred_date = models.DateField(
        null=True, blank=True,
        verbose_name="Date de consultation souhaitée"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
        db_index=True,
        verbose_name="Statut"
    )

    admin_notes = models.TextField(
        blank=True,
        verbose_name="Notes internes (admin uniquement)"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de demande")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande de consultation"
        verbose_name_plural = "Demandes de consultation"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.get_consultation_type_display()} ({self.get_status_display()})"

    def get_type_icon(self):
        icons = {
            "visa_etude": "🎓",
            "visa_travail": "💼",
            "residence_permanente": "🏠",
            "langue": "🗣️",
            "allemand": "🇩🇪",
            "cv": "📄",
            "profil": "👤",
            "job_search": "🔍",
            "autre": "💬",
        }
        return icons.get(self.consultation_type, "📋")


class ImmigrationAlertSubscriber(models.Model):
    """Contact qui veut recevoir des alertes utiles pour son projet immigration."""

    PROJECT_CHOICES = [
        ("study", "Visa études"),
        ("work", "Travail"),
        ("scholarship", "Bourses"),
        ("language", "Tests de langue"),
        ("documents", "Documents"),
        ("news", "Actualités immigration"),
    ]

    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("both", "Email + WhatsApp"),
    ]

    email = models.EmailField("Email", blank=True)
    whatsapp = models.CharField("WhatsApp", max_length=40, blank=True)
    country = models.CharField("Pays visé", max_length=80, blank=True)
    project_type = models.CharField(
        "Projet",
        max_length=30,
        choices=PROJECT_CHOICES,
        default="news",
        db_index=True,
    )
    channel = models.CharField(
        "Canal",
        max_length=20,
        choices=CHANNEL_CHOICES,
        default="email",
    )
    is_active = models.BooleanField("Actif", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Abonné alerte immigration"
        verbose_name_plural = "Abonnés alertes immigration"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["email", "whatsapp", "project_type", "country"],
                name="uniq_core_alert_subscriber_contact_project_country",
            )
        ]

    def __str__(self):
        contact = self.email or self.whatsapp or "contact sans coordonnée"
        return f"{contact} - {self.get_project_type_display()}"
