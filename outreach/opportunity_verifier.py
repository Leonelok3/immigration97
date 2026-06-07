from dataclasses import dataclass, field
from urllib.parse import urlparse

from outreach.ai_employer_scraper import POSITIVE_SIGNALS, SECTOR_KEYWORDS


TRUSTED_HOST_HINTS = {
    "greenhouse.io": 10,
    "lever.co": 10,
    "workdayjobs.com": 10,
    "smartrecruiters.com": 10,
    "successfactors": 8,
    "jobbank.gc.ca": 18,
    "canada.ca": 18,
    "immigration.govt.nz": 18,
    "seek.co.nz": 8,
    "seek.com.au": 8,
    "gov.uk": 16,
    "make-it-in-germany.com": 12,
}

COUNTRY_SIGNAL_TERMS = {
    "CA": ["canada", "ontario", "quebec", "toronto", "montreal", "lmia", "job bank"],
    "NZ": ["new zealand", "aotearoa", "auckland", "christchurch", "accredited employer"],
    "AU": ["australia", "sydney", "melbourne", "brisbane", "482 visa", "tss visa"],
    "GB": ["united kingdom", "uk", "england", "skilled worker visa", "certificate of sponsorship"],
    "FR": ["france", "paris", "lyon"],
    "DE": ["germany", "deutschland", "berlin", "make it in germany"],
    "BE": ["belgium", "belgique", "brussels"],
    "CH": ["switzerland", "suisse", "zurich", "geneva"],
    "IE": ["ireland", "dublin", "critical skills"],
    "NL": ["netherlands", "amsterdam", "highly skilled migrant"],
}


@dataclass
class VerificationResult:
    score: int
    decision: str
    signals: list[str] = field(default_factory=list)
    notes: str = ""


def _contains_any(text: str, terms: list[str]) -> list[str]:
    lower = (text or "").lower()
    return [term for term in terms if term.lower() in lower]


def verify_employer_lead(lead) -> VerificationResult:
    text = " ".join(
        [
            lead.title or "",
            lead.company_name or "",
            lead.location or "",
            lead.visa_signal or "",
            lead.evidence_text or "",
            lead.job_url or "",
            lead.website or "",
        ]
    )
    lower = text.lower()
    parsed = urlparse(lead.job_url or lead.website or "")
    host = parsed.netloc.lower()

    score = int(getattr(lead, "confidence_score", 0) or 0)
    signals: list[str] = []

    if lead.company_name:
        score += 8
        signals.append("employeur nommé")
    if lead.website:
        score += 6
        signals.append("site employeur détecté")
    if lead.contact_email and lead.website:
        email_domain = lead.contact_email.split("@")[-1].lower()
        site_domain = urlparse(lead.website).netloc.lower().removeprefix("www.")
        if email_domain and site_domain and email_domain in site_domain:
            score += 10
            signals.append("email cohérent avec le domaine")

    for host_hint, weight in TRUSTED_HOST_HINTS.items():
        if host_hint in host:
            score += weight
            signals.append(f"source reconnue: {host_hint}")

    visa_hits = [signal for signal in POSITIVE_SIGNALS if signal in lower]
    if visa_hits:
        score += min(20, len(visa_hits) * 5)
        signals.append("signal mobilité: " + ", ".join(visa_hits[:3]))

    sector_terms = SECTOR_KEYWORDS.get(lead.sector, [])
    sector_hits = _contains_any(lower, sector_terms)
    if sector_hits:
        score += min(10, len(sector_hits) * 2)
        signals.append("secteur cohérent: " + ", ".join(sector_hits[:3]))

    country_hits = _contains_any(lower, COUNTRY_SIGNAL_TERMS.get(lead.country, []))
    if country_hits:
        score += min(12, len(country_hits) * 4)
        signals.append("pays cohérent: " + ", ".join(country_hits[:3]))

    if not lead.company_name:
        score -= 12
        signals.append("employeur à identifier")
    if not lead.evidence_text:
        score -= 15
        signals.append("preuve textuelle absente")

    score = max(0, min(score, 100))
    if score >= 75:
        decision = "verified"
        notes = "Opportunité solide à présenter après revue rapide."
    elif score >= 50:
        decision = "review"
        notes = "Opportunité intéressante, validation humaine recommandée."
    else:
        decision = "weak"
        notes = "Signal insuffisant; garder en observation ou rejeter."

    return VerificationResult(score=score, decision=decision, signals=signals[:8], notes=notes)
