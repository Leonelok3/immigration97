# cv_generator/services/openai_service.py

import logging
from services.ai_service import AIService

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    Service IA centralisé – sécurisé, tolérant aux erreurs,
    prêt production Immigration97.
    """

    def _call(self, system_prompt: str, user_prompt: str, temperature=0.4):
        return AIService().chat_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            task_type="visa",
        )

    # ==========================
    # 🧠 RÉSUMÉ PROFESSIONNEL
    # ==========================
    def generate_career_summaries(self, job_title, years, industry, country):
        prompt = f"""
Rédige 3 résumés professionnels pour un CV {country}.

Poste : {job_title}
Secteur : {industry}
Objectif : Immigration / emploi qualifié

Contraintes :
- 3 à 5 lignes max
- Ton professionnel, crédible recruteur
- Compatible ATS
- Sans âge, sans photo, sans informations sensibles
"""
        text = self._call(
            system_prompt="Tu es un expert RH immigration Canada/Europe.",
            user_prompt=prompt,
        )
        return [t.strip("-• ") for t in text.split("\n") if len(t.strip()) > 20][:3]

    # ==========================
    # 🛠️ AMÉLIORER UNE EXPÉRIENCE
    # ==========================
    def enhance_experience_description(self, raw, job_title, industry, clarifications=None):
        prompt = f"""
Transforme cette expérience en bullet points ATS.

Poste : {job_title}
Secteur : {industry}

Texte brut :
{raw}

Contraintes :
- 4 à 6 bullet points
- Verbes d’action
- Résultats mesurables si possible
- Format Canada / Europe
"""
        return self._call(
            system_prompt="Tu es un recruteur senior spécialisé immigration.",
            user_prompt=prompt,
            temperature=0.3,
        )

    # ==========================
    # 🧩 QUESTIONS CLARIFIANTES
    # ==========================
    def generate_clarifying_questions(self, raw, job_title, industry):
        prompt = f"""
Pose 4 questions pour améliorer cette expérience CV.

Poste : {job_title}
Secteur : {industry}
Texte :
{raw}
"""
        text = self._call(
            system_prompt="Tu aides un candidat à améliorer son CV.",
            user_prompt=prompt,
        )
        return [q.strip("-• ") for q in text.split("\n") if q.strip()]

    # ==========================
    # ⚙️ OPTIMISATION COMPÉTENCES
    # ==========================
    def optimize_skills(self, skills, job_title, industry, country):
        prompt = f"""
Optimise ces compétences pour un CV {country}.

Poste : {job_title}
Secteur : {industry}
Compétences : {', '.join(skills)}

Retourne :
- compétences techniques
- soft skills
- mots-clés ATS
"""
        text = self._call(
            system_prompt="Tu es un expert ATS et recrutement international.",
            user_prompt=prompt,
        )
        return {
            "raw": text
        }
