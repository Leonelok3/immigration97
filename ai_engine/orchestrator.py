from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentRoute:
    key: str
    name: str
    category: str
    description: str
    url: str
    priority: int
    free_mode: bool = True


AGENT_ROUTES: tuple[AgentRoute, ...] = (
    AgentRoute(
        key="student_visa",
        name="Agent Visa Etudes",
        category="Etudes",
        description="Analyse le projet d'etudes, le budget, le pays cible, les admissions et la checklist visa.",
        url="/visa-etudes/parcours/",
        priority=95,
    ),
    AgentRoute(
        key="student_destinations",
        name="Agent Pays & Programmes",
        category="Etudes",
        description="Compare Canada, France, Belgique, Allemagne et autres destinations selon le profil et les guides disponibles.",
        url="/visa-etudes/pays/",
        priority=88,
    ),
    AgentRoute(
        key="job_application",
        name="Agent Candidature Internationale",
        category="Emploi",
        description="Relie les offres, le profil candidat, le CV, la lettre, l'email et le suivi de candidature.",
        url="/jobs/",
        priority=94,
    ),
    AgentRoute(
        key="ats_cv",
        name="Agent ATS CV + Lettre",
        category="Documents",
        description="Adapte gratuitement le CV, la lettre et l'email a une offre avec score ATS et mots-cles manquants.",
        url="/jobs/offres-publiques/",
        priority=92,
    ),
    AgentRoute(
        key="profile_visibility",
        name="Agent Profil Talent",
        category="Talents",
        description="Aide le candidat a publier un profil clair, complet et visible par les recruteurs.",
        url="/profiles/me/",
        priority=84,
    ),
    AgentRoute(
        key="permanent_residence",
        name="Agent Residence Permanente",
        category="Immigration",
        description="Oriente vers le diagnostic RP Canada, les scores et les prochaines actions.",
        url="/pr/eligibilite/",
        priority=90,
    ),
    AgentRoute(
        key="language_tests",
        name="Agents Tests de Langue",
        category="Langues",
        description="Prepare TEF, TCF, anglais et allemand avec cours, examens blancs, progression et coach.",
        url="/prep/",
        priority=86,
    ),
    AgentRoute(
        key="resources",
        name="Agent Ressources & Guides",
        category="Ressources",
        description="Dirige vers les guides PDF, checklists, modeles et documents telechargeables.",
        url="/ressources/",
        priority=76,
    ),
    AgentRoute(
        key="consultation",
        name="Agent Consultation Humaine",
        category="Accompagnement",
        description="Escalade vers un accompagnement humain quand le dossier est complexe ou urgent.",
        url="/consultation/",
        priority=80,
    ),
)


INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "student_visa": (
        "etude",
        "etudes",
        "etudiant",
        "universite",
        "admission",
        "bourse",
        "campus",
        "visa etudiant",
    ),
    "student_destinations": (
        "pays",
        "destination",
        "france",
        "canada",
        "belgique",
        "allemagne",
        "universite",
        "programme",
    ),
    "job_application": (
        "emploi",
        "job",
        "offre",
        "recruteur",
        "postuler",
        "candidature",
        "travail",
        "sponsor",
        "lmia",
    ),
    "ats_cv": (
        "cv",
        "lettre",
        "motivation",
        "ats",
        "email",
        "adapter",
        "document",
        "pdf",
    ),
    "profile_visibility": (
        "profil",
        "talent",
        "visible",
        "invitation",
        "portfolio",
        "competence",
        "competences",
    ),
    "permanent_residence": (
        "residence",
        "rp",
        "permanent",
        "entree express",
        "express entry",
        "crs",
        "pnp",
    ),
    "language_tests": (
        "tef",
        "tcf",
        "ielts",
        "toefl",
        "anglais",
        "francais",
        "allemand",
        "test de langue",
        "langue",
    ),
    "resources": (
        "guide",
        "ressource",
        "checklist",
        "modele",
        "telecharger",
        "pdf",
    ),
    "consultation": (
        "urgent",
        "bloque",
        "bloqué",
        "aide",
        "coach",
        "consultation",
        "accompagnement",
        "expert",
    ),
}


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _user_context(user: Any) -> dict[str, Any]:
    context: dict[str, Any] = {
        "authenticated": bool(getattr(user, "is_authenticated", False)),
        "profile_complete": False,
        "category": "",
        "language_level": "",
        "has_public_profile": False,
    }
    if not context["authenticated"]:
        return context

    try:
        profile = getattr(user, "profile", None)
        if profile:
            context["profile_complete"] = bool(
                getattr(profile, "headline", "")
                and getattr(profile, "bio", "")
                and getattr(profile, "category_id", None)
            )
            context["category"] = str(getattr(profile, "category", "") or "")
            context["language_level"] = str(getattr(profile, "level", "") or "")
            context["has_public_profile"] = bool(getattr(profile, "is_public", False))
    except Exception:
        pass

    return context


def _score_routes(goal: str, context: dict[str, Any]) -> list[tuple[int, AgentRoute, list[str]]]:
    text = _normalize(goal)
    scored: list[tuple[int, AgentRoute, list[str]]] = []

    for route in AGENT_ROUTES:
        matched = [kw for kw in INTENT_KEYWORDS.get(route.key, ()) if kw in text]
        score = route.priority + (len(matched) * 18)

        if not text and route.key in {"profile_visibility", "job_application", "student_visa"}:
            score += 12
        if context.get("category") and route.key in {"job_application", "ats_cv"}:
            score += 10
        if not context.get("profile_complete") and route.key == "profile_visibility":
            score += 18
        if context.get("has_public_profile") and route.key == "job_application":
            score += 8

        scored.append((score, route, matched))

    return sorted(scored, key=lambda item: item[0], reverse=True)


def _next_steps(routes: list[AgentRoute], context: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    keys = {route.key for route in routes}

    if not context.get("profile_complete"):
        steps.append("Completer le profil talent: metier/categorie, titre, bio, localisation, competences et documents.")
    if "job_application" in keys or "ats_cv" in keys:
        steps.append("Choisir une offre pertinente, lancer l'adaptation ATS, relire le CV et la lettre, puis postuler.")
    if "student_visa" in keys:
        steps.append("Renseigner le profil etudiant, choisir 1 a 2 pays cibles, puis suivre la checklist visa etudes.")
    if "language_tests" in keys:
        steps.append("Faire un test de niveau, travailler les cours recommandes et refaire un examen blanc apres correction.")
    if "permanent_residence" in keys:
        steps.append("Calculer le diagnostic RP, verifier les points faibles, puis preparer les preuves prioritaires.")
    if "resources" in keys:
        steps.append("Telecharger les guides PDF et checklists correspondant au pays et au type de dossier.")

    if not steps:
        steps.append("Commencer par le profil utilisateur, puis choisir le parcours: etudes, emploi, residence permanente ou tests de langue.")

    return steps[:5]


def orchestrate_immigration97(user: Any = None, goal: str = "") -> dict[str, Any]:
    context = _user_context(user)
    scored = _score_routes(goal, context)
    selected = [route for _score, route, _matched in scored[:4]]
    primary = selected[0] if selected else AGENT_ROUTES[0]

    return {
        "goal": goal,
        "context": context,
        "primary_agent": primary,
        "recommended_agents": selected,
        "signals": [
            {"agent": route.name, "score": score, "matches": matched}
            for score, route, matched in scored[:6]
        ],
        "next_steps": _next_steps(selected, context),
        "mode": "rules_free",
        "summary": (
            "Orchestrateur gratuit actif: il route l'utilisateur vers les meilleurs agents "
            "Immigration97 sans consommer de credits API."
        ),
    }

