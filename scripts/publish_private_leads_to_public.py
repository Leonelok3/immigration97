from job_agent.models import JobLead, PublicJobOffer

created = 0
updated = 0

for lead in JobLead.objects.exclude(url="").order_by("-created_at"):
    obj, was_created = PublicJobOffer.objects.update_or_create(
        url=lead.url,
        defaults={
            "source": lead.source or "Job Agent",
            "title": lead.title or "Offre",
            "company": lead.company or "Entreprise",
            "location": lead.location or "International",
            "description_text": lead.description_text or "",
            "is_active": True,
        },
    )
    if was_created:
        created += 1
    else:
        updated += 1

print(
    "published_from_private",
    created,
    "created",
    updated,
    "updated",
    "public_active",
    PublicJobOffer.objects.filter(is_active=True).count(),
)
