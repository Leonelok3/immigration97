from dataclasses import dataclass, field
from urllib.parse import urlparse


FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
}

HIGH_RISK_TERMS = {
    "processing fee": 28,
    "registration fee": 26,
    "visa fee upfront": 32,
    "pay before interview": 35,
    "western union": 34,
    "moneygram": 34,
    "crypto": 30,
    "bitcoin": 30,
    "guaranteed visa": 35,
    "guaranteed job": 28,
    "no interview required": 32,
    "urgent payment": 30,
    "work permit guaranteed": 32,
    "frais de dossier": 24,
    "payer avant": 30,
    "visa garanti": 35,
    "emploi garanti": 28,
    "sans entretien": 30,
}

MEDIUM_RISK_TERMS = {
    "whatsapp only": 14,
    "telegram": 14,
    "send passport": 16,
    "passport copy": 14,
    "bank details": 18,
    "personal documents": 12,
    "contact on whatsapp": 12,
    "agency fee": 16,
    "admin fee": 14,
    "frais administratifs": 14,
    "envoyez votre passeport": 18,
    "documents personnels": 12,
}

PROTECTIVE_TERMS = {
    "official careers": -10,
    "equal opportunity employer": -8,
    "job bank": -18,
    "government": -12,
    "accredited employer": -12,
    "greenhouse.io": -8,
    "lever.co": -8,
    "workdayjobs.com": -8,
}


@dataclass
class ScamAssessmentResult:
    risk_score: int
    risk_level: str
    flags: list[str] = field(default_factory=list)
    recommendation: str = ""


def assess_scam_risk(lead) -> ScamAssessmentResult:
    text = " ".join(
        [
            lead.title or "",
            lead.company_name or "",
            lead.location or "",
            lead.visa_signal or "",
            lead.evidence_text or "",
            lead.job_url or "",
            lead.website or "",
            lead.contact_email or "",
        ]
    )
    lower = text.lower()
    score = 10
    flags: list[str] = []

    for term, weight in HIGH_RISK_TERMS.items():
        if term in lower:
            score += weight
            flags.append(f"alerte forte: {term}")

    for term, weight in MEDIUM_RISK_TERMS.items():
        if term in lower:
            score += weight
            flags.append(f"alerte moyenne: {term}")

    for term, weight in PROTECTIVE_TERMS.items():
        if term in lower:
            score += weight
            flags.append(f"signal rassurant: {term}")

    email = (lead.contact_email or "").lower()
    if email:
        domain = email.split("@")[-1]
        if domain in FREE_EMAIL_DOMAINS:
            score += 18
            flags.append("email gratuit non corporate")
        elif lead.website:
            site_domain = urlparse(lead.website).netloc.lower().removeprefix("www.")
            if site_domain and domain not in site_domain:
                score += 10
                flags.append("email différent du domaine employeur")
    else:
        score += 8
        flags.append("email recruteur absent")

    job_host = urlparse(lead.job_url or "").netloc.lower()
    site_host = urlparse(lead.website or "").netloc.lower()
    if lead.website and lead.job_url and site_host and site_host not in job_host and job_host not in site_host:
        trusted_boards = ("greenhouse.io", "lever.co", "workdayjobs.com", "smartrecruiters.com")
        if not any(board in job_host for board in trusted_boards):
            score += 8
            flags.append("URL offre différente du site employeur")

    if not lead.company_name:
        score += 12
        flags.append("nom employeur absent")

    if getattr(lead, "confidence_score", 0) >= 75:
        score -= 8
        flags.append("score opportunité élevé")

    score = max(0, min(score, 100))
    if score >= 70:
        level = "high"
        recommendation = "Ne pas recommander au candidat avant vérification humaine complète."
    elif score >= 40:
        level = "medium"
        recommendation = "Demander une vérification manuelle avant diffusion."
    else:
        level = "low"
        recommendation = "Risque faible; vérifier quand même le site officiel avant candidature."

    return ScamAssessmentResult(
        risk_score=score,
        risk_level=level,
        flags=flags[:10],
        recommendation=recommendation,
    )
