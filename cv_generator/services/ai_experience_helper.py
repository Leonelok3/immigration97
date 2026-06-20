from services.ai_service import AIService


def improve_experience_description(
    title,
    company,
    raw_text,
    language="fr"
):
    if not raw_text:
        return ""

    prompt = f"""
Tu es un expert en recrutement au Canada.

Améliore la description suivante pour un CV canadien :
- style professionnel
- compatible ATS
- phrases courtes
- verbes d’action
- résultats mesurables si possible
- pas d’informations inventées

Poste : {title}
Entreprise : {company}

Texte original :
{raw_text}

Rends la réponse sous forme de liste à puces.
"""

    if language == "en":
        prompt = prompt.replace("Tu es un expert en recrutement au Canada.", 
                                 "You are a Canadian recruitment expert.")
        prompt = prompt.replace("Améliore la description suivante", 
                                 "Improve the following job description")
        prompt = prompt.replace("Rends la réponse sous forme de liste à puces.",
                                 "Return the result as bullet points.")

    return AIService().generate_response(prompt, task_type="visa")["response"]
