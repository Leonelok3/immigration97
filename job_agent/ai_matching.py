import numpy as np
from services.ai_service import AIService, AIServiceError

def get_embedding(text: str):
    return AIService().create_embedding(text)

def semantic_match(cv_text: str, offer_text: str):
    if not cv_text or not offer_text:
        return 0

    try:
        emb_cv = np.array(get_embedding(cv_text))
        emb_offer = np.array(get_embedding(offer_text))
    except AIServiceError:
        return 0

    similarity = np.dot(emb_cv, emb_offer) / (
        np.linalg.norm(emb_cv) * np.linalg.norm(emb_offer)
    )

    score = int(similarity * 100)
    return max(0, min(score, 100))
