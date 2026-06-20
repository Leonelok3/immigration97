from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from actualite.models import NewsItem, Tag
from actualite.services.official_news_collector import canonical_url, collect_official_news


class Command(BaseCommand):
    help = "Collecte 12 actualités immigration récentes depuis des sources officielles, sans OpenAI."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=12)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"]), 50))
        candidates = collect_official_news(limit=limit)

        tag, _ = Tag.objects.get_or_create(name="Source officielle", defaults={"slug": "source-officielle"})
        created = updated = skipped = 0

        for item in candidates:
            source_key = canonical_url(item.url)
            if not source_key:
                skipped += 1
                continue

            existing = NewsItem.objects.filter(external_link__iexact=source_key).first()
            if not existing:
                existing = NewsItem.objects.filter(external_link__iexact=item.url).first()

            self.stdout.write(f"{item.country} | {item.category} | {item.title} -> {item.url}")
            if options["dry_run"]:
                skipped += 1
                continue

            defaults = {
                "title": item.title,
                "category": item.category,
                "country_target": item.country,
                "summary": item.summary,
                "content": (
                    f"{item.summary}\n\n"
                    f"Information vérifiée depuis une source officielle: {item.source_label}.\n\n"
                    f"Lien officiel: {item.url}"
                ),
                "external_link": source_key,
                "is_published": True,
                "is_important": item.category in {"law", "alert", "conference"},
                "publish_date": item.published_at or timezone.now(),
            }

            if existing:
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save()
                existing.tags.add(tag)
                updated += 1
            else:
                news = NewsItem.objects.create(**defaults)
                news.tags.add(tag)
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Actualités officielles: {created} créées, {updated} mises à jour, {skipped} ignorées/dry-run."
            )
        )
