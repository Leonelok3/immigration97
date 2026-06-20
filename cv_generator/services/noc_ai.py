from services.ai_service import AIService

def generate_noc_tasks(job_title, language="fr"):
    """
    Génère des tâches professionnelles compatibles ATS Canada
    """

    system_prompt = (
        "Tu es un expert en recrutement canadien et en systèmes ATS. "
        "Tu connais parfaitement les descriptions de postes selon la logique NOC Canada. "
        "Tu écris des tâches professionnelles claires, réalistes et optimisées ATS."
    )

    user_prompt = (
        f"Génère une liste de 6 à 8 tâches professionnelles pour le poste suivant :\n"
        f"POSTE : {job_title}\n\n"
        f"Contraintes :\n"
        f"- Style CV Canada\n"
        f"- Langage ATS\n"
        f"- Verbes d’action\n"
        f"- Tâches concrètes\n"
        f"- Pas de phrases longues\n"
        f"- Langue : {'français' if language == 'fr' else 'anglais'}\n\n"
        f"Format attendu : liste à puces"
    )

    return AIService().chat_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task_type="faq",
    )
