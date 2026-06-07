LANGUAGE_POINTS = {
    "none": 0,
    "a1": 3,
    "a2": 6,
    "b1": 12,
    "b2": 20,
    "c1": 26,
    "c2": 30,
}

EDUCATION_POINTS = {
    "none": 0,
    "secondary": 8,
    "vocational": 14,
    "bachelor": 20,
    "master": 24,
    "phd": 26,
}

SECTOR_JOB_MAP = {
    "agriculture": ["Ouvrier agricole", "Préposé serre", "Ouvrier transformation alimentaire", "Conducteur d'engins agricoles"],
    "construction": ["Manœuvre BTP", "Soudeur", "Électricien aide", "Plombier aide", "Charpentier"],
    "sante": ["Aide-soignant", "Préposé aux bénéficiaires", "Caregiver", "Infirmier avec équivalence"],
    "logistique": ["Préparateur de commandes", "Magasinier", "Cariste", "Chauffeur avec permis adapté"],
    "hotellerie": ["Cuisinier", "Aide-cuisinier", "Serveur", "Housekeeper", "Réceptionniste"],
    "tech": ["Développeur", "Support IT", "Technicien réseau", "Data analyst junior"],
    "industrie": ["Opérateur de production", "Technicien maintenance", "Machiniste", "Soudeur industriel"],
    "education": ["Assistant éducatif", "Formateur", "Enseignant avec équivalence"],
    "finance": ["Assistant comptable", "Comptable junior", "Paie"],
    "commerce": ["Vendeur", "Conseiller client", "Business developer junior"],
    "services": ["Agent entretien", "Facility assistant", "Agent sécurité", "Support client"],
    "autre": ["Travailleur polyvalent", "Assistant opérationnel"],
}

COUNTRY_RULES = {
    "CA": {
        "label": "Canada",
        "min_score": 58,
        "strong_sectors": {"agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie"},
        "required": ["Passeport", "CV canadien ATS", "Preuves d'expérience", "Niveau anglais/français documenté"],
    },
    "NZ": {
        "label": "Nouvelle-Zélande",
        "min_score": 55,
        "strong_sectors": {"agriculture", "construction", "sante", "hotellerie", "industrie", "logistique"},
        "required": ["Passeport", "CV anglais", "Preuves d'expérience", "Cible employeur accrédité"],
    },
    "AU": {
        "label": "Australie",
        "min_score": 62,
        "strong_sectors": {"construction", "sante", "tech", "industrie", "education", "hotellerie"},
        "required": ["Passeport", "CV anglais", "Anglais B1/B2+", "Certificats métier"],
    },
    "GB": {
        "label": "Royaume-Uni",
        "min_score": 64,
        "strong_sectors": {"sante", "tech", "education", "construction", "hotellerie"},
        "required": ["Passeport", "CV anglais", "Anglais B1/B2+", "Employeur sponsor licencié"],
    },
    "DE": {
        "label": "Allemagne",
        "min_score": 60,
        "strong_sectors": {"sante", "construction", "tech", "industrie", "education"},
        "required": ["Passeport", "CV européen", "Diplômes/certificats", "Allemand ou anglais selon métier"],
    },
    "BE": {
        "label": "Belgique",
        "min_score": 56,
        "strong_sectors": {"construction", "sante", "logistique", "hotellerie", "tech", "industrie"},
        "required": ["Passeport", "CV européen", "Preuves d'expérience", "Offre employeur"],
    },
    "FR": {
        "label": "France",
        "min_score": 56,
        "strong_sectors": {"construction", "sante", "hotellerie", "industrie", "services", "tech"},
        "required": ["Passeport", "CV français", "Preuves d'expérience", "Diplômes si métier réglementé"],
    },
}

EU_EXPANSION = ["GB", "DE", "BE", "FR"]


def expand_preferred_countries(raw: str) -> list[str]:
    result: list[str] = []
    for item in (raw or "").split(","):
        code = item.strip().upper()
        if not code:
            continue
        if code == "EU":
            result.extend(EU_EXPANSION)
        else:
            result.append(code)
    return [code for code in dict.fromkeys(result) if code in COUNTRY_RULES]


def _budget_points(value: str) -> int:
    return {"low": 2, "medium": 8, "good": 13, "strong": 16}.get(value, 6)


def _experience_points(years: int) -> int:
    if years >= 5:
        return 22
    if years >= 3:
        return 18
    if years >= 1:
        return 12
    return 0


def _age_points(age: int) -> int:
    if 20 <= age <= 35:
        return 14
    if 36 <= age <= 44:
        return 10
    if 18 <= age <= 19 or 45 <= age <= 50:
        return 6
    return 2


def evaluate_job_visa_profile(data: dict) -> dict:
    sector = data.get("sector") or "autre"
    age = int(data.get("age") or 0)
    years = int(data.get("years_experience") or 0)
    french = data.get("french_level") or "none"
    english = data.get("english_level") or "none"
    education = data.get("education_level") or "none"
    budget = data.get("budget") or "medium"
    has_passport = bool(data.get("has_passport"))
    has_cv = bool(data.get("has_cv"))
    certificates = (data.get("certificates") or "").strip()

    base_score = (
        _age_points(age)
        + _experience_points(years)
        + EDUCATION_POINTS.get(education, 0)
        + max(LANGUAGE_POINTS.get(french, 0), LANGUAGE_POINTS.get(english, 0))
        + _budget_points(budget)
        + (8 if has_passport else 0)
        + (8 if has_cv else 0)
        + (4 if certificates else 0)
    )
    readiness_score = max(0, min(base_score, 100))

    countries = []
    for code in expand_preferred_countries(data.get("preferred_countries", "")) or ["CA", "NZ", "AU", "GB", "DE", "BE", "FR"]:
        rule = COUNTRY_RULES[code]
        country_score = readiness_score
        reasons = []
        if sector in rule["strong_sectors"]:
            country_score += 8
            reasons.append("secteur demandé dans ce pays")
        if code in {"NZ", "AU", "GB"} and LANGUAGE_POINTS.get(english, 0) < LANGUAGE_POINTS["b1"]:
            country_score -= 14
            reasons.append("anglais à renforcer")
        if code in {"DE"} and LANGUAGE_POINTS.get(english, 0) < LANGUAGE_POINTS["b1"] and LANGUAGE_POINTS.get(french, 0) < LANGUAGE_POINTS["b1"]:
            country_score -= 8
            reasons.append("langue européenne à renforcer")
        if code in {"CA", "BE", "FR"} and LANGUAGE_POINTS.get(french, 0) >= LANGUAGE_POINTS["b1"]:
            country_score += 6
            reasons.append("français utile")
        country_score = max(0, min(country_score, 100))
        if country_score >= rule["min_score"]:
            level = "recommandé"
        elif country_score >= rule["min_score"] - 12:
            level = "possible après renforcement"
        else:
            level = "à préparer"
        countries.append(
            {
                "code": code,
                "label": rule["label"],
                "score": country_score,
                "level": level,
                "reasons": reasons or ["profil à comparer avec les offres vérifiées"],
            }
        )

    countries.sort(key=lambda item: item["score"], reverse=True)

    missing = []
    if not has_passport:
        missing.append("Passeport valide")
    if not has_cv:
        missing.append("CV international adapté au pays cible")
    if years < 1:
        missing.append("Preuves d'expérience professionnelle")
    if LANGUAGE_POINTS.get(english, 0) < LANGUAGE_POINTS["b1"] and any(c["code"] in {"NZ", "AU", "GB"} for c in countries[:3]):
        missing.append("Anglais niveau B1/B2 ou test officiel selon le pays")
    if not certificates:
        missing.append("Diplômes, attestations ou certificats métier")
    if budget in {"low", "medium"}:
        missing.append("Budget documenté pour démarches, traductions et premiers frais")

    accessible_jobs = SECTOR_JOB_MAP.get(sector, SECTOR_JOB_MAP["autre"])[:]
    if years < 2:
        accessible_jobs = [f"{job} junior / assistant" for job in accessible_jobs[:4]]

    action_plan = []
    if not has_passport:
        action_plan.append("Faire ou renouveler le passeport avant toute candidature internationale.")
    if not has_cv:
        action_plan.append("Créer un CV ATS adapté Canada/Europe/Australie avec expériences chiffrées.")
    action_plan.append("Cibler 2 pays maximum au départ et sélectionner 10 opportunités vérifiées.")
    if LANGUAGE_POINTS.get(english, 0) < LANGUAGE_POINTS["b1"]:
        action_plan.append("Monter l'anglais au moins au niveau B1 pour Nouvelle-Zélande, Australie et Royaume-Uni.")
    if years < 3:
        action_plan.append("Rassembler attestations de travail, contrats, fiches de paie ou références employeurs.")
    action_plan.append("Postuler uniquement aux offres avec preuve officielle et risque anti-arnaque faible ou moyen.")

    if readiness_score >= 75:
        summary = "Profil solide pour commencer les candidatures internationales avec ciblage pays."
    elif readiness_score >= 55:
        summary = "Profil exploitable, mais quelques éléments doivent être renforcés avant de postuler massivement."
    else:
        summary = "Profil à préparer: il faut consolider documents, langue, CV ou expérience avant les candidatures."

    return {
        "readiness_score": readiness_score,
        "recommended_countries": countries[:5],
        "accessible_jobs": accessible_jobs,
        "missing_documents": missing,
        "action_plan": action_plan,
        "summary": summary,
    }
