import json
import os
import urllib.error
import urllib.request

from services.ai_service import AIService


def _mock_response(user_prompt: str) -> str:
    p = (user_prompt or "").upper()

    if " CE " in f" {p} ":
        return json.dumps(
            {
                "reading_text": "Bonjour, je m'appelle Lina. J'habite à Lyon.",
                "questions": [
                    {
                        "question": "Où habite Lina ?",
                        "choices": ["Paris", "Lyon", "Lille", "Nice"],
                        "correct_answer": "B",
                    }
                ],
            },
            ensure_ascii=False,
        )

    if " EO " in f" {p} ":
        return json.dumps(
            {
                "topic": "Se présenter",
                "instructions": "Parlez de vous pendant 2 minutes.",
                "expected_points": ["identité", "profession", "objectifs"],
            },
            ensure_ascii=False,
        )

    if " EE " in f" {p} ":
        return json.dumps(
            {
                "topic": "Mon projet professionnel",
                "instructions": "Rédigez un texte structuré.",
                "min_words": 120,
                "sample_answer": "Je souhaite évoluer dans un environnement international.",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "audio_script": "Bonjour. Aujourd'hui, nous parlons du travail.",
            "questions": [
                {
                    "question": "Sujet principal ?",
                    "choices": ["Sport", "Travail", "Cuisine", "Voyage"],
                    "correct_answer": "B",
                }
            ],
        },
        ensure_ascii=False,
    )


def _http_post_json(url: str, headers: dict, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LLM HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM network error: {e}") from e


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    return AIService(timeout=int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))).chat_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task_type="analyse",
    )


def _call_azure_openai(system_prompt: str, user_prompt: str) -> str:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

    if not endpoint or not api_key or not deployment:
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY / AZURE_OPENAI_DEPLOYMENT are required."
        )

    url = (
        f"{endpoint}/openai/deployments/{deployment}/chat/completions"
        f"?api-version={api_version}"
    )

    payload = {
        "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    data = _http_post_json(
        url=url,
        headers={"api-key": api_key},
        payload=payload,
        timeout=timeout,
    )

    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"Unexpected Azure OpenAI response format: {data}") from e


def call_llm(system_prompt: str, user_prompt: str) -> str:
    # Priorité dev local
    if os.getenv("LLM_MOCK_MODE", "0").strip() == "1":
        return _mock_response(user_prompt)

    provider = os.getenv("LLM_PROVIDER", "OPENAI").strip().upper()

    if provider == "OPENAI":
        return _call_openai(system_prompt, user_prompt)
    if provider == "AZURE_OPENAI":
        return _call_azure_openai(system_prompt, user_prompt)

    raise RuntimeError("Unsupported LLM_PROVIDER. Use OPENAI or AZURE_OPENAI.")
