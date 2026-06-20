import json
import os
import re
from dataclasses import dataclass
from typing import Any


COMMON_WORDS = {
    "avec", "dans", "pour", "vous", "nous", "elle", "leur", "leurs", "des", "les",
    "une", "the", "and", "for", "with", "that", "this", "from", "poste", "offre",
    "entreprise", "experience", "expérience", "candidat", "candidate", "travail",
    "mission", "missions", "recherche", "profil", "competence", "compétence",
}

ACTION_VERBS_FR = [
    "Développé", "Optimisé", "Administré", "Maintenu", "Automatisé", "Analysé",
    "Coordonné", "Documenté", "Sécurisé", "Accompagné",
]


@dataclass
class CoachResult:
    tailored_cv_text: str
    generated_letter: str
    email_subject: str
    generated_email: str
    suggested_answers: dict[str, str]
    ats_score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    coach_notes: str
    ai_status: str


def _clean_text(value: Any, limit: int = 12000) -> str:
    text = str(value or "").replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:limit]


def _tokens(text: str) -> list[str]:
    text = _clean_text(text).lower()
    text = re.sub(r"[^a-z0-9àâäçéèêëîïôöùûüœæ+#.\s-]", " ", text)
    raw = re.split(r"[\s,;/|()]+", text)
    out = []
    for token in raw:
        token = token.strip(".-")
        if len(token) < 3 or token in COMMON_WORDS:
            continue
        out.append(token)
    return out


def _top_keywords(offer_text: str, limit: int = 18) -> list[str]:
    counts: dict[str, int] = {}
    for token in _tokens(offer_text):
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _count in ranked[:limit]]


def _keyword_match(cv_text: str, offer_text: str) -> tuple[int, list[str], list[str]]:
    keywords = _top_keywords(offer_text)
    cv_tokens = set(_tokens(cv_text))
    matched = [kw for kw in keywords if kw.lower() in cv_tokens]
    missing = [kw for kw in keywords if kw.lower() not in cv_tokens]
    score = int(round((len(matched) / max(1, len(keywords))) * 100))
    return max(0, min(score, 100)), matched, missing


def analyze_cv_quality(cv_text: str) -> dict[str, Any]:
    text = _clean_text(cv_text, 200000)
    tokens = _tokens(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    words_count = len(re.findall(r"\w+", text, flags=re.UNICODE))
    keywords = _top_keywords(text, limit=16)

    has_email = bool(re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text))
    has_phone = bool(re.search(r"(\+?\d[\d\s().-]{7,}\d)", text))
    has_experience = any(
        word in text.lower()
        for word in ["expérience", "experience", "emploi", "poste", "projet", "réalisation", "mission"]
    )
    has_skills = any(
        word in text.lower()
        for word in ["compétence", "competence", "skills", "outils", "technologies", "savoir-faire"]
    )

    warnings = []
    if not text:
        warnings.append("Aucun texte CV disponible.")
    elif words_count < 80:
        warnings.append("Le CV texte semble trop court ou le PDF est peut-être scanné/non extractible.")
    if text and not has_experience:
        warnings.append("Aucune section expérience/projet détectée.")
    if text and not has_skills:
        warnings.append("Aucune section compétences/outils détectée.")
    if text and not (has_email or has_phone):
        warnings.append("Aucun contact clair détecté dans le texte.")

    score = 0
    if words_count >= 80:
        score += 30
    if words_count >= 250:
        score += 20
    if has_experience:
        score += 20
    if has_skills:
        score += 15
    if has_email or has_phone:
        score += 15

    status = "empty"
    if score >= 75:
        status = "good"
    elif score >= 45:
        status = "medium"
    elif words_count:
        status = "weak"

    return {
        "status": status,
        "score": max(0, min(score, 100)),
        "words_count": words_count,
        "lines_count": len(lines),
        "keywords": keywords,
        "warnings": warnings,
        "has_text": bool(text),
    }


def _split_keywords(value: str) -> list[str]:
    items = []
    for part in re.split(r"[,;\n]+", value or ""):
        part = part.strip(" .-")
        if len(part) >= 2 and part.lower() not in COMMON_WORDS:
            items.append(part)
    return items


def _best_lines_for_keywords(cv_text: str, keywords: list[str], limit: int = 8) -> list[str]:
    lines = []
    for raw in (cv_text or "").splitlines():
        line = raw.strip(" -•\t")
        if len(line) < 20:
            continue
        score = sum(1 for kw in keywords if kw.lower() in line.lower())
        if score:
            lines.append((score, line))
    ranked = sorted(lines, key=lambda item: (-item[0], len(item[1])))
    return [line for _score, line in ranked[:limit]]


def _make_free_ats_cv(
    *,
    candidate_name: str,
    offer_title: str,
    company: str,
    location: str,
    cv_text: str,
    matched: list[str],
    missing: list[str],
) -> str:
    matched_line = ", ".join(matched[:10]) if matched else "compétences transférables, motivation, adaptation"
    missing_line = ", ".join(missing[:8]) if missing else "aucun mot-clé prioritaire identifié"
    evidence_lines = _best_lines_for_keywords(cv_text, matched + missing)

    if not evidence_lines and cv_text.strip():
        evidence_lines = [
            line.strip(" -•\t")
            for line in cv_text.splitlines()
            if len(line.strip()) >= 25
        ][:6]

    bullets = []
    for idx, line in enumerate(evidence_lines[:6]):
        verb = ACTION_VERBS_FR[idx % len(ACTION_VERBS_FR)]
        if line.lower().startswith(tuple(v.lower() for v in ACTION_VERBS_FR)):
            bullets.append(f"- {line}")
        else:
            bullets.append(f"- {verb}: {line}")

    if not bullets:
        bullets = [
            "- Ajoutez ici une expérience réelle liée à l'offre.",
            "- Précisez vos outils, responsabilités, résultats et années d'expérience.",
            "- Renforcez le CV avec les mots-clés manquants uniquement s'ils correspondent à votre parcours.",
        ]

    return f"""CV ADAPTÉ ATS

{candidate_name}
Cible: {offer_title}{(" - " + company) if company else ""}
Localisation cible: {location or "À préciser"}

RÉSUMÉ PROFESSIONNEL CIBLÉ
Profil orienté {offer_title}, avec une candidature alignée sur les besoins de {company or "l'entreprise"}. Les points forts à mettre en avant sont: {matched_line}. Le CV doit rester honnête et ne renforcer que les compétences réellement maîtrisées.

COMPÉTENCES À METTRE EN AVANT
{matched_line}

EXPÉRIENCES / RÉALISATIONS À PRIORISER
{chr(10).join(bullets)}

MOTS-CLÉS ATS À AJOUTER SI VRAIS
{missing_line}

VERSION DE TRAVAIL
{cv_text.strip() if cv_text.strip() else "Collez le texte de votre CV dans Job Agent > Documents pour obtenir une version plus complète."}
""".strip()


def _make_free_letter(
    *,
    candidate_name: str,
    offer_title: str,
    company: str,
    location: str,
    matched: list[str],
    missing: list[str],
    base_letter: str,
) -> str:
    strengths = ", ".join(matched[:6]) if matched else "mon sérieux, ma capacité d'apprentissage et mon sens du résultat"
    improvement = ", ".join(missing[:4]) if missing else "les exigences du poste"
    base = f"\n\nÉléments personnels à intégrer si pertinents:\n{base_letter.strip()}" if base_letter.strip() else ""
    return f"""Objet : Candidature au poste de {offer_title}

Madame, Monsieur,

Je vous adresse ma candidature pour le poste de {offer_title}{(" à " + location) if location else ""}{(" au sein de " + company) if company else ""}. Votre offre a retenu mon attention parce qu'elle correspond à un projet professionnel clair : mettre mes compétences au service d'une équipe structurée, exigeante et orientée résultats.

Mon profil présente plusieurs points d'alignement avec vos besoins, notamment : {strengths}. Dans mes expériences et projets, j'ai appris à travailler avec rigueur, à respecter les consignes, à progresser rapidement et à livrer un travail fiable. Je souhaite aujourd'hui mobiliser ces acquis dans un environnement professionnel où la qualité, la ponctualité et la capacité d'adaptation sont essentielles.

Je suis également attentif aux compétences attendues dans votre annonce, en particulier : {improvement}. Lorsque ces éléments correspondent à mon parcours réel, je peux les détailler en entretien avec des exemples concrets. Lorsque certains points demandent encore à être renforcés, je suis prêt à me former rapidement et à suivre les méthodes de votre équipe.

Au-delà des compétences techniques, je souhaite vous apporter une candidature sérieuse, stable et motivée. Je suis disponible pour un entretien afin de vous présenter plus concrètement mon parcours, ma compréhension du poste et la manière dont je peux contribuer à vos objectifs dès les premières semaines.

Cordialement,
{candidate_name}{base}
""".strip()


def _make_free_email(*, offer_title: str, company: str, candidate_name: str) -> tuple[str, str]:
    subject = f"Candidature - {offer_title}{(' - ' + company) if company else ''}"
    greeting = f"Bonjour {company}," if company else "Bonjour Madame, Monsieur,"
    body = f"""{greeting}

Je me permets de vous transmettre ma candidature pour le poste de {offer_title}.

Vous trouverez ci-joint mon CV adapté ainsi que ma lettre de motivation. J'ai pris soin de préparer un dossier ciblé sur les missions et compétences mentionnées dans votre annonce, afin de faciliter votre lecture et de vous présenter une candidature claire.

Je suis disponible pour un entretien, un échange téléphonique ou tout complément d'information. Je peux également fournir rapidement des précisions sur mes expériences, mes disponibilités et ma motivation pour ce poste.

Merci pour votre attention et pour le temps accordé à ma candidature.

Cordialement,
{candidate_name}
"""
    return subject, body.strip()


def _make_interview_guide(
    *,
    candidate_name: str,
    offer_title: str,
    company: str,
    location: str,
    matched: list[str],
    missing: list[str],
) -> str:
    strengths = ", ".join(matched[:6]) if matched else "fiabilité, apprentissage rapide, sens du service, organisation"
    gaps = ", ".join(missing[:5]) if missing else "aucun point bloquant identifié"
    employer = company or "l'entreprise"
    place = f" à {location}" if location else ""
    return f"""GUIDE ENTRETIEN - {offer_title}

Objectif de l'entretien
Montrer que {candidate_name} comprend le poste, sait expliquer son parcours avec des preuves concrètes et peut contribuer rapidement chez {employer}{place}.

Pitch de présentation en 60 secondes
Bonjour, je m'appelle {candidate_name}. Je candidate au poste de {offer_title}. Mon parcours m'a permis de développer une méthode de travail sérieuse, structurée et orientée résultats. Ce qui m'intéresse dans cette opportunité, c'est la possibilité d'utiliser mes compétences dans un cadre concret, de progresser avec votre équipe et de contribuer à des missions utiles dès les premières semaines.

Forces à défendre
1. Compétences alignées avec l'offre: {strengths}.
2. Capacité d'adaptation: expliquer une situation où vous avez appris vite.
3. Fiabilité: donner un exemple où vous avez respecté consignes, délais ou qualité.
4. Motivation internationale: expliquer pourquoi vous êtes prêt(e) à vous engager sérieusement.

Questions probables et réponses à préparer
1. Parlez-moi de vous.
Réponse: présenter le parcours en 3 blocs: métier, expériences utiles, objectif actuel.

2. Pourquoi ce poste vous intéresse ?
Réponse: relier le poste à vos compétences, au secteur de l'entreprise et à votre projet professionnel.

3. Que savez-vous de notre entreprise ?
Réponse: citer le secteur, le service ou produit, le pays/ville, puis expliquer pourquoi cela vous intéresse.

4. Quelles expériences prouvent que vous pouvez réussir ?
Réponse: préparer 2 exemples concrets avec contexte, action, résultat.

5. Quelles sont vos forces ?
Réponse: choisir 3 forces liées à l'offre: {strengths}.

6. Quels points devez-vous encore renforcer ?
Réponse: rester honnête. Points possibles à travailler: {gaps}. Ajouter que vous apprenez vite et donnez une méthode d'apprentissage.

7. Êtes-vous disponible ?
Réponse: donner une disponibilité claire, puis confirmer votre flexibilité pour entretien, test ou documents.

8. Pourquoi devrait-on vous choisir ?
Réponse: combiner motivation, fiabilité, compétences utiles et volonté de contribuer rapidement.

Questions à poser au recruteur
1. Quelles sont les priorités du poste pendant les 30 premiers jours ?
2. Quels outils ou méthodes l'équipe utilise-t-elle au quotidien ?
3. Quelles qualités font réussir une personne dans ce poste ?
4. Quelle est la prochaine étape du processus de recrutement ?

Checklist avant entretien
- Relire l'annonce et noter 5 mots-clés importants.
- Préparer 2 exemples d'expérience avec résultats.
- Préparer une réponse claire sur disponibilité, salaire et mobilité.
- Garder CV, lettre, lien annonce et notes Immigration97 ouverts.
- Ne jamais inventer: si un point manque, expliquer comment vous allez le renforcer.
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _fallback_pack(
    *,
    offer_title: str,
    company: str,
    location: str,
    offer_text: str,
    cv_text: str,
    base_letter: str,
    language: str,
    candidate_name: str,
) -> CoachResult:
    score, matched, missing = _keyword_match(cv_text, offer_text)
    missing_line = ", ".join(missing[:8]) if missing else "aucun mot-clé prioritaire"
    strengths = ", ".join(matched[:6]) if matched else "ma fiabilité, mon sérieux, ma capacité d'apprentissage et mon sens du résultat"
    tailored_cv = _make_free_ats_cv(
        candidate_name=candidate_name,
        offer_title=offer_title,
        company=company,
        location=location,
        cv_text=cv_text,
        matched=matched,
        missing=missing,
    )
    letter = _make_free_letter(
        candidate_name=candidate_name,
        offer_title=offer_title,
        company=company,
        location=location,
        matched=matched,
        missing=missing,
        base_letter=base_letter,
    )
    email_subject, email_body = _make_free_email(
        offer_title=offer_title,
        company=company,
        candidate_name=candidate_name,
    )
    interview_guide = _make_interview_guide(
        candidate_name=candidate_name,
        offer_title=offer_title,
        company=company,
        location=location,
        matched=matched,
        missing=missing,
    )

    notes = (
        f"Score ATS estimé: {score}/100.\n\n"
        "Priorité 1 - Vérifier l'offre: titre, entreprise, lieu, exigences obligatoires et canal officiel de candidature.\n"
        "Priorité 2 - Adapter honnêtement le CV: reprendre uniquement les mots-clés réellement maîtrisés, puis ajouter des preuves concrètes.\n"
        "Priorité 3 - Personnaliser la lettre: garder un ton professionnel, montrer la compréhension du poste et éviter les phrases trop générales.\n"
        "Priorité 4 - Postuler: envoyer CV + lettre + email, puis noter la date de candidature dans le kanban.\n"
        "Priorité 5 - Préparer l'entretien: apprendre à expliquer 3 expériences, 3 forces, 1 faiblesse maîtrisée et sa disponibilité.\n\n"
        f"Mots-clés à renforcer seulement si vrais dans le parcours: {missing_line}."
    )

    return CoachResult(
        tailored_cv_text=tailored_cv.strip(),
        generated_letter=letter.strip(),
        email_subject=email_subject.strip(),
        generated_email=email_body.strip(),
        suggested_answers={
            "Pitch entretien - Présentez-vous": (
                f"Bonjour, je m'appelle {candidate_name}. Je candidate au poste de {offer_title}. "
                "Mon parcours m'a permis de développer une approche sérieuse, organisée et orientée résultats. "
                f"Ce poste m'intéresse parce qu'il correspond à mes compétences et à mon objectif de contribuer concrètement aux besoins de {company or 'votre entreprise'}."
            ),
            "Motivation": (
                f"Je suis motivé(e) par le poste de {offer_title} parce qu'il me permet d'utiliser mes compétences utiles, "
                "de progresser dans un cadre professionnel et de contribuer à des missions concrètes. "
                "J'ai pris le temps de lire l'offre et je peux expliquer en entretien comment mon profil répond aux besoins."
            ),
            "Disponibilité": (
                "Je suis disponible selon les conditions du poste et je peux m'organiser rapidement pour un entretien, "
                "un test ou une prise de poste. Ma disponibilité exacte peut être confirmée selon le contrat proposé."
            ),
            "Prétentions salariales": (
                "Je reste ouvert(e) à une proposition alignée avec les responsabilités du poste, le niveau attendu, "
                "les conditions de travail et les standards du marché local."
            ),
            "Forces à défendre": (
                f"Mettre en avant: {', '.join(matched[:8]) if matched else 'fiabilité, apprentissage rapide, communication, sens du résultat'}. "
                "Préparer un exemple concret pour chaque force avant l'entretien."
            ),
            "Points à renforcer": f"Ajouter seulement si réel dans le CV ou l'entretien: {missing_line}.",
            "Relance après candidature": (
                f"Bonjour, je me permets de faire suite à ma candidature au poste de {offer_title}. "
                "Je reste très intéressé(e) par cette opportunité et disponible pour un entretien ou toute information complémentaire. "
                f"Cordialement, {candidate_name}"
            ),
            "Message LinkedIn recruteur": (
                f"Bonjour, je me permets de vous contacter concernant le poste de {offer_title}. "
                "Je suis intéressé(e) par cette opportunité et j'ai préparé un CV ciblé sur les besoins de l'offre. "
                "Serait-il possible de vous transmettre ma candidature ou de connaître la meilleure personne à contacter ? "
                f"Cordialement, {candidate_name}"
            ),
            "Lettre courte - version portail": (
                f"Je souhaite présenter ma candidature au poste de {offer_title}. "
                f"Mon profil correspond à plusieurs besoins de l'offre, notamment {strengths}. "
                "Je suis motivé(e), disponible pour échanger et prêt(e) à contribuer sérieusement aux missions confiées."
            ),
            "Checklist avant envoi": (
                "1. Vérifier que le CV contient les compétences réellement maîtrisées.\n"
                "2. Personnaliser le nom de l'entreprise dans la lettre et l'email.\n"
                "3. Joindre CV et lettre au bon format PDF.\n"
                "4. Vérifier l'email recruteur ou le portail officiel.\n"
                "5. Noter la date de candidature dans le kanban Immigration97.\n"
                "6. Préparer une relance après quelques jours si aucune réponse."
            ),
            "Guide entretien complet": interview_guide,
        },
        ats_score=score,
        matched_keywords=matched,
        missing_keywords=missing,
        coach_notes=notes,
        ai_status="ats_free",
    )


def generate_tailored_application(
    *,
    offer_title: str,
    company: str,
    location: str,
    offer_text: str,
    cv_text: str,
    base_letter: str,
    language: str,
    candidate_name: str,
) -> CoachResult:
    offer_title = _clean_text(offer_title, 220) or "Poste"
    company = _clean_text(company, 220)
    location = _clean_text(location, 220)
    offer_text = _clean_text(offer_text)
    cv_text = _clean_text(cv_text)
    base_letter = _clean_text(base_letter, 6000)
    language = (language or "fr").lower()
    candidate_name = _clean_text(candidate_name, 160) or "Candidat"

    fallback = _fallback_pack(
        offer_title=offer_title,
        company=company,
        location=location,
        offer_text=offer_text,
        cv_text=cv_text,
        base_letter=base_letter,
        language=language,
        candidate_name=candidate_name,
    )

    if os.getenv("ATS_FREE_MODE", "1").strip() != "0":
        return fallback

    try:
        from ai_engine.services.llm_service import call_llm

        system_prompt = (
            "Tu es ApplicationCoachAgent d'Immigration97, un coach premium de candidature "
            "pour candidats africains et internationaux. Ton objectif est de produire un "
            "dossier professionnel prêt à relire: CV ATS ciblé, lettre de motivation solide, "
            "email de candidature, réponses d'entretien, relance et conseils d'action. "
            "Tu dois rester strictement honnête: ne jamais inventer une expérience, un diplôme, "
            "une certification, une nationalité, un permis de travail ou une compétence non présente "
            "dans le CV. Si un élément de l'offre manque dans le CV, indique-le comme point à renforcer "
            "ou à vérifier, sans le présenter comme acquis. Ton style doit être professionnel, humain, "
            "concret, orienté preuves et adapté au marché international. Retourne uniquement un JSON valide."
        )
        user_prompt = f"""
Langue de sortie: {language}

CANDIDAT:
Nom: {candidate_name}
CV actuel:
{cv_text or "CV texte indisponible"}

Lettre de base:
{base_letter or "Aucune lettre de base"}

OFFRE:
Titre: {offer_title}
Entreprise: {company}
Lieu: {location}
Description:
{offer_text or "Description indisponible"}

Retourne exactement ce JSON:
{{
  "tailored_cv_text": "CV complet adapté à l'offre, structuré ATS avec titre ciblé, résumé professionnel, compétences clés, expériences reformulées, mots-clés honnêtes, sans mensonge",
  "generated_letter": "Lettre de motivation professionnelle de 5 à 7 paragraphes: accroche ciblée, compréhension de l'offre, preuves du profil, motivation, disponibilité, conclusion",
  "email_subject": "Objet email court et professionnel",
  "generated_email": "Email de candidature professionnel de 3 à 5 paragraphes, clair, poli, prêt à envoyer",
  "suggested_answers": {{
    "Pitch entretien - Présentez-vous": "...",
    "Motivation": "...",
    "Disponibilité": "...",
    "Prétentions salariales": "...",
    "Forces à défendre": "...",
    "Points à renforcer": "...",
    "Relance après candidature": "..."
  }},
  "ats_score": 0,
  "matched_keywords": ["..."],
  "missing_keywords": ["..."],
  "coach_notes": "Plan d'action concret avant d'envoyer: vérifier offre, adapter CV, relire lettre/email, postuler, noter statut, préparer entretien"
}}
"""
        raw = call_llm(system_prompt, user_prompt)
        payload = _extract_json(raw)
        if not payload:
            return fallback

        return CoachResult(
            tailored_cv_text=_clean_text(payload.get("tailored_cv_text")) or fallback.tailored_cv_text,
            generated_letter=_clean_text(payload.get("generated_letter"), 9000) or fallback.generated_letter,
            email_subject=_clean_text(payload.get("email_subject"), 200) or fallback.email_subject,
            generated_email=_clean_text(payload.get("generated_email"), 6000) or fallback.generated_email,
            suggested_answers=payload.get("suggested_answers") if isinstance(payload.get("suggested_answers"), dict) else fallback.suggested_answers,
            ats_score=max(0, min(int(payload.get("ats_score") or fallback.ats_score), 100)),
            matched_keywords=payload.get("matched_keywords") if isinstance(payload.get("matched_keywords"), list) else fallback.matched_keywords,
            missing_keywords=payload.get("missing_keywords") if isinstance(payload.get("missing_keywords"), list) else fallback.missing_keywords,
            coach_notes=_clean_text(payload.get("coach_notes"), 3000) or fallback.coach_notes,
            ai_status="ai",
        )
    except Exception:
        return fallback
