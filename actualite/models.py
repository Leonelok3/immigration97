from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.urls import reverse


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:80]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class NewsItem(models.Model):
    CATEGORY_CHOICES = [
        ("job", "Offres d'emploi"),
        ("law", "Loi & Immigration"),
        ("conference", "Conférences & Événements"),
        ("opportunity", "Opportunités"),
        ("advice", "Conseils"),
        ("alert", "Alertes"),
    ]

    COUNTRY_CHOICES = [
        ("US", "USA"),
        ("CA", "Canada"),
        ("DE", "Allemagne"),
        ("EU", "Europe"),
        ("IT", "Italie"),
        ("FR", "France"),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    country_target = models.CharField(max_length=2, choices=COUNTRY_CHOICES)
    city = models.CharField(max_length=80, blank=True)

    summary = models.TextField(help_text="Résumé court (SEO + cartes)")
    content = models.TextField(help_text="Article complet (texte long)")

    # Image : upload + url externe
    featured_image = models.ImageField(
        upload_to="actualite/images/",
        blank=True,
        null=True,
        help_text="Image upload (recommandé en production)",
    )
    external_image_url = models.URLField(blank=True, help_text="Alternative si pas d'upload (ex: CDN)")

    video_url = models.URLField(blank=True, help_text="YouTube/Vimeo/MP4 URL (optionnel)")
    external_link = models.URLField(blank=True, help_text="Source officielle (recommandé)")

    tags = models.ManyToManyField(Tag, blank=True, related_name="news_items")

    # ✅ Badges éditoriaux
    is_featured = models.BooleanField(default=False, verbose_name="À la une")
    is_urgent = models.BooleanField(default=False, verbose_name="Urgent")
    is_important = models.BooleanField(default=False, verbose_name="Important")

    is_published = models.BooleanField(default=True)

    publish_date = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    views_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-publish_date"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["category"]),
            models.Index(fields=["country_target"]),
            models.Index(fields=["-publish_date"]),
            models.Index(fields=["is_published", "-publish_date"]),
            models.Index(fields=["is_urgent", "-publish_date"]),
            models.Index(fields=["is_important", "-publish_date"]),
            models.Index(fields=["-views_count"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:220] or "news"
            slug = base
            i = 2
            while NewsItem.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("actualite:detail", kwargs={"slug": self.slug})

    @property
    def image_url(self) -> str:
        if self.featured_image:
            return self.featured_image.url
        if self.external_image_url:
            return self.external_image_url
        return ""

    @property
    def reading_time_minutes(self) -> int:
        # estimation : ~200 mots / minute
        words = len((self.content or "").split())
        return max(1, round(words / 200))


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    country_interest = models.CharField(max_length=10, blank=True, default="")  # ex: "US", "CA"
    source_page = models.CharField(max_length=40, blank=True, default="")      # ex: "list", "country", "detail"
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Newsletter"
        verbose_name_plural = "Newsletters"

    def __str__(self):
        return self.email
