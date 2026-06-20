from services.ai_service import AIService

def translate_cv_text(text, source_lang, target_lang, job_title):
    """
    Traduction professionnelle CV Canada (ATS-safe)
    """

    prompt = f"""
You are a professional Canadian resume translator.

Task:
Translate the following resume content from {source_lang} to {target_lang}.

Rules:
- Use Canadian resume standards
- ATS compatible wording
- Keep professional tone
- No literal translation
- Adapt terminology to the job role
- Do NOT add information
- Do NOT remove information
- No emojis

Job title:
{job_title}

Text:
{text}
"""

    return AIService().generate_response(prompt, task_type="visa")["response"]
