"""
Service d'évaluation IA pour EO (Expression Orale) et EE (Expression Écrite).

- transcribe_audio() : Whisper API → transcription texte
- evaluate_eo()      : GPT → score + feedback sur prise de parole
- evaluate_ee()      : GPT → score + corrections + version corrigée
"""
import json
import logging
import os
import re
from services.ai_service import AIService
from json import JSONDecodeError

logger = logging.getLogger(__name__)

_MOCK_MODE = os.getenv("LLM_MOCK_MODE", "0") == "1"


# ──────────────────────────────────────────────
# MOCK RESPONSES
# ──────────────────────────────────────────────

_MOCK_TRANSCRIPT = (
    "Je pense que la vie en ville offre de nombreux avantages. "
    "Premièrement, les transports en commun sont très accessibles, "
    "ce qui facilite les déplacements quotidiens. Deuxièmement, "
    "on trouve facilement des services comme les hôpitaux, les écoles "
    "et les commerces. Cependant, la pollution et le bruit peuvent être "
    "des inconvénients importants. En conclusion, il faut peser le pour "
    "et le contre avant de choisir entre la ville et la campagne."
)

_MOCK_EO_RESULT = {
    "score": 72,
    "feedback": (
        "Bonne structure générale avec une introduction claire et une conclusion. "
        "Le vocabulaire est adapté au niveau demandé. "
        "Quelques imprécisions grammaticales, mais le message reste clair."
    ),
    "points_covered": [
        "Introduction avec prise de position",
        "Arguments développés avec exemples",
        "Conclusion synthétique",
    ],
    "suggestions": [
        "Enrichir le vocabulaire avec des connecteurs logiques variés",
        "Développer davantage les exemples concrets",
        "Soigner la prononciation des liaisons",
    ],
}

_MOCK_EE_RESULT = {
    "score": 68,
    "feedback": (
        "La production est cohérente et répond globalement à la consigne. "
        "La structure est correcte. Quelques erreurs de grammaire et un "
        "vocabulaire qui pourrait être plus riche."
    ),
    "errors": [
        {"original": "je suis allé au magasin hier", "correction": "je suis allé au magasin hier.", "rule": "Ponctuation"},
        {"original": "les gens ils veulent", "correction": "les gens veulent", "rule": "Éviter le pronom redondant"},
    ],
    "corrected_version": (
        "Madame, Monsieur,\n\n"
        "Je vous écris pour vous faire part de ma situation. "
        "Je suis arrivé au Canada il y a six mois et je souhaite m'inscrire "
        "à des cours de français. Pourriez-vous m'indiquer les démarches à suivre ?\n\n"
        "Dans l'attente de votre réponse, je vous adresse mes cordiales salutations."
    ),
}


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    text = (raw or "").strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1].strip()
    return json.loads(text)


# ──────────────────────────────────────────────
# TRANSCRIPTION WHISPER
# ──────────────────────────────────────────────

def transcribe_audio(audio_path: str, language: str = "fr") -> str:
    """
    Transcrit un fichier audio en texte via Whisper (OpenAI).
    Retourne une transcription mock si LLM_MOCK_MODE=1.
    language: code ISO 639-1 (fr, en, de, it…)
    """
    if _MOCK_MODE:
        logger.info("[MOCK] transcribe_audio → mock transcript")
        return _MOCK_TRANSCRIPT

    try:
        return AIService().transcribe_audio(audio_path, language=language)
    except Exception as e:
        logger.error("Whisper transcription failed: %s", e)
        raise RuntimeError(f"Transcription audio échouée: {e}") from e


# ──────────────────────────────────────────────
# ÉVALUATION EO
# ──────────────────────────────────────────────

_EO_EVAL_SYSTEM = """
Tu es un examinateur expert en expression orale française, spécialisé dans les examens TEF/TCF/DELF.

Ta mission : évaluer la transcription d'une prise de parole d'un étudiant.

Critères d'évaluation (total 100 points) :
- Pertinence (25 pts) : le sujet est-il traité, les points attendus sont-ils abordés ?
- Structure (20 pts) : introduction, développement, conclusion ?
- Vocabulaire (25 pts) : richesse, précision, registre adapté ?
- Grammaire (20 pts) : corrections des structures, conjugaisons, accords ?
- Cohérence (10 pts) : enchaînement des idées, connecteurs ?

Contraintes STRICTES :
- Retourne UNIQUEMENT un JSON valide.
- Aucun texte en dehors du JSON.
- Format exact ci-dessous.

Format attendu :
{
  "score": 75,
  "feedback": "Évaluation globale en 2-3 phrases",
  "points_covered": ["Point abordé 1", "Point abordé 2"],
  "suggestions": ["Conseil d'amélioration 1", "Conseil d'amélioration 2"],
  "criteria": {
    "pertinence": 20,
    "structure": 15,
    "vocabulaire": 18,
    "grammaire": 16,
    "coherence": 6
  }
}
"""


def evaluate_eo(
    transcript: str,
    topic: str,
    instructions: str,
    level: str,
    expected_points: list | None = None,
) -> dict:
    """
    Évalue une transcription EO via GPT.
    Retourne : {score, feedback, points_covered, suggestions, criteria}
    """
    if _MOCK_MODE:
        logger.info("[MOCK] evaluate_eo → mock result")
        return _MOCK_EO_RESULT

    from ai_engine.services.llm_service import call_llm

    pts_str = "\n".join(f"- {p}" for p in (expected_points or [])) or "(non spécifiés)"
    user_prompt = (
        f"Sujet : {topic}\n"
        f"Consigne : {instructions}\n"
        f"Niveau CECR attendu : {level}\n"
        f"Points attendus :\n{pts_str}\n\n"
        f"Transcription de l'étudiant :\n{transcript}\n\n"
        "Évalue cette prise de parole selon les critères définis."
    )

    try:
        raw = call_llm(system_prompt=_EO_EVAL_SYSTEM, user_prompt=user_prompt)
        return _extract_json(raw)
    except Exception as e:
        logger.error("EO evaluation failed: %s", e)
        return {
            "score": 50,
            "feedback": "Évaluation non disponible. Réessaie dans quelques instants.",
            "points_covered": [],
            "suggestions": [],
            "criteria": {},
        }


# ──────────────────────────────────────────────
# ÉVALUATION EE
# ──────────────────────────────────────────────

_EE_EVAL_SYSTEM = """
Tu es un correcteur expert en expression écrite française, spécialisé dans les examens TEF/TCF/DELF.

Ta mission : évaluer et corriger la production écrite d'un étudiant.

Critères d'évaluation (total 100 points) :
- Tâche accomplie (25 pts) : la consigne est-elle respectée, le registre est-il approprié ?
- Structure (20 pts) : organisation, paragraphes, cohérence globale ?
- Vocabulaire (25 pts) : richesse, précision, absence de répétitions ?
- Grammaire (30 pts) : conjugaisons, accords, ponctuation, syntaxe ?

Contraintes STRICTES :
- Retourne UNIQUEMENT un JSON valide.
- Aucun texte en dehors du JSON.
- Format exact ci-dessous.

Format attendu :
{
  "score": 72,
  "feedback": "Évaluation globale en 2-3 phrases",
  "errors": [
    {"original": "texte original avec erreur", "correction": "texte corrigé", "rule": "Règle grammaticale"}
  ],
  "corrected_version": "Version intégrale corrigée du texte de l'étudiant",
  "criteria": {
    "tache": 18,
    "structure": 15,
    "vocabulaire": 20,
    "grammaire": 19
  }
}
"""


def evaluate_ee(
    text: str,
    topic: str,
    instructions: str,
    level: str,
) -> dict:
    """
    Évalue une production écrite EE via GPT.
    Retourne : {score, feedback, errors, corrected_version, criteria}
    """
    if _MOCK_MODE:
        logger.info("[MOCK] evaluate_ee → mock result")
        return _MOCK_EE_RESULT

    from ai_engine.services.llm_service import call_llm

    user_prompt = (
        f"Sujet : {topic}\n"
        f"Consigne : {instructions}\n"
        f"Niveau CECR attendu : {level}\n\n"
        f"Texte de l'étudiant :\n{text}\n\n"
        "Évalue et corrige cette production écrite selon les critères définis."
    )

    try:
        raw = call_llm(system_prompt=_EE_EVAL_SYSTEM, user_prompt=user_prompt)
        return _extract_json(raw)
    except Exception as e:
        logger.error("EE evaluation failed: %s", e)
        return {
            "score": 50,
            "feedback": "Évaluation non disponible. Réessaie dans quelques instants.",
            "errors": [],
            "corrected_version": text,
            "criteria": {},
        }
