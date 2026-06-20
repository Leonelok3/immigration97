"""Centralized OpenAI access layer with caching and cost controls."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Literal, Mapping, TypedDict

from django.conf import settings
from django.core.cache import cache
from dotenv import load_dotenv

try:
    from openai import (
        APIConnectionError,
        APIError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        OpenAI,
        OpenAIError,
        RateLimitError,
    )
except Exception:  # pragma: no cover - handled at runtime when dependency is absent
    APIConnectionError = APIError = APIStatusError = APITimeoutError = AuthenticationError = None
    OpenAI = OpenAIError = RateLimitError = None


logger = logging.getLogger(__name__)

TaskType = Literal["faq", "visa", "analyse"]


class ChatMessage(TypedDict):
    """Compact representation of a chat message sent to the model."""

    role: str
    content: str


class AIResponse(TypedDict, total=False):
    """Structured response returned by ``generate_response``."""

    response: str
    model_used: str
    tokens_used: int
    cache_hit: bool
    task_type: str
    local_faq_hit: bool
    error: str


class UsageStats(TypedDict):
    """Aggregate usage information stored in Django cache."""

    calls: int
    tokens_consumed: int
    cache_savings: int
    estimated_cost: float


@dataclass(frozen=True)
class ModelRoute:
    """Model, prompt and token policy for a task family."""

    model: str
    system_prompt: str
    max_tokens: int


class AIServiceError(RuntimeError):
    """Base error for AI service failures."""


class AIServiceConfigurationError(AIServiceError):
    """Raised when OpenAI is not configured correctly."""


class AIServiceTimeoutError(AIServiceError):
    """Raised when an OpenAI request times out."""


class AIServiceQuotaError(AIServiceError):
    """Raised when quota or rate limits prevent completion."""


class AIServiceAuthenticationError(AIServiceError):
    """Raised when the configured API key is invalid."""


class AIServiceUnavailableError(AIServiceError):
    """Raised when OpenAI is temporarily unavailable."""


class AIService:
    """Production-oriented AI gateway for Immigration97.

    It centralizes model routing, Django caching, short prompts, local FAQ
    fallback, usage stats and OpenAI error handling so app code does not call
    OpenAI directly.
    """

    CACHE_TIMEOUT_SECONDS = 60 * 60 * 24
    RESPONSE_CACHE_PREFIX = "ai_service:response:"
    USAGE_CACHE_KEY = "ai_service:usage_stats"

    ROUTES: Mapping[TaskType, ModelRoute] = {
        "faq": ModelRoute(
            model="gpt-4o-mini",
            system_prompt="Tu es un assistant immigration précis. Réponds brièvement.",
            max_tokens=150,
        ),
        "visa": ModelRoute(
            model="gpt-4.1-mini",
            system_prompt="Tu es expert immigration. Donne des réponses claires et pratiques.",
            max_tokens=300,
        ),
        "analyse": ModelRoute(
            model="gpt-4.1",
            system_prompt="Tu es consultant immigration expert. Analyse avec précision.",
            max_tokens=800,
        ),
    }

    ESTIMATED_COST_PER_1K_TOKENS: Mapping[str, Decimal] = {
        "gpt-4o-mini": Decimal("0.0006"),
        "gpt-4.1-mini": Decimal("0.002"),
        "gpt-4.1": Decimal("0.02"),
    }

    LOCAL_FAQ: Mapping[str, str] = {
        "quels documents pour un visa canada": (
            "Les documents courants sont un passeport valide, preuves de fonds, "
            "lettre d'explication, justificatifs de situation, photos et formulaires requis."
        ),
        "combien de temps pour un visa": (
            "Les délais varient selon le pays, le type de visa et la période. "
            "Vérifie toujours le délai officiel avant de déposer ton dossier."
        ),
        "comment améliorer mon dossier immigration": (
            "Renforce les preuves de fonds, la cohérence du projet, les documents officiels, "
            "les tests de langue et les liens avec ton pays ou ton projet d'accueil."
        ),
        "c'est quoi entree express": (
            "Entrée Express est le système canadien de gestion des demandes pour certains "
            "programmes d'immigration économique."
        ),
        "faut-il un test de langue": (
            "Oui, beaucoup de programmes exigent un test officiel comme TEF, TCF, IELTS ou CELPIP."
        ),
    }

    def __init__(self, api_key: str | None = None, timeout: float | None = None) -> None:
        load_dotenv(getattr(settings, "BASE_DIR", os.getcwd()) / ".env")
        self.api_key = (
            api_key
            or getattr(settings, "OPENAI_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
        ).strip()
        self.timeout = timeout or float(getattr(settings, "OPENAI_TIMEOUT_SECONDS", 30))
        self._client: Any | None = None

    def generate_response(
        self,
        user_input: str,
        task_type: str,
        conversation_history: list[ChatMessage] | None = None,
    ) -> AIResponse:
        """Generate an optimized AI response for the given task type."""

        normalized_task = self._normalize_task_type(task_type)
        route = self.ROUTES[normalized_task]
        clean_input = (user_input or "").strip()
        if not clean_input:
            raise ValueError("user_input cannot be empty.")

        local_answer = self._lookup_local_faq(clean_input)
        if local_answer:
            self._record_usage(tokens_used=0, estimated_cost=Decimal("0"), cache_savings=1)
            self._log_usage(route.model, 0, False, normalized_task)
            return {
                "response": local_answer,
                "model_used": "local_faq",
                "tokens_used": 0,
                "cache_hit": False,
                "task_type": normalized_task,
                "local_faq_hit": True,
            }

        optimized_history = self._optimize_history(conversation_history or [])
        cache_key = self._cache_key(clean_input, normalized_task, optimized_history)
        cached = cache.get(cache_key)
        if cached:
            cached_response = dict(cached)
            cached_response["cache_hit"] = True
            self._record_usage(tokens_used=0, estimated_cost=Decimal("0"), cache_savings=1)
            self._log_usage(route.model, 0, True, normalized_task)
            return cached_response

        messages: list[ChatMessage] = [{"role": "system", "content": route.system_prompt}]
        messages.extend(optimized_history)
        messages.append({"role": "user", "content": clean_input})

        try:
            completion = self._client_instance().chat.completions.create(
                model=route.model,
                messages=messages,
                temperature=0.3,
                max_tokens=route.max_tokens,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise self._map_openai_error(exc) from exc

        text = (completion.choices[0].message.content or "").strip()
        tokens_used = int(getattr(getattr(completion, "usage", None), "total_tokens", 0) or 0)
        estimated_cost = self._estimate_cost(route.model, tokens_used)

        result: AIResponse = {
            "response": text,
            "model_used": route.model,
            "tokens_used": tokens_used,
            "cache_hit": False,
            "task_type": normalized_task,
            "local_faq_hit": False,
        }
        cache.set(cache_key, result, self.CACHE_TIMEOUT_SECONDS)
        self._record_usage(tokens_used=tokens_used, estimated_cost=estimated_cost, cache_savings=0)
        self._log_usage(route.model, tokens_used, False, normalized_task)
        return result

    def get_usage_stats(self) -> UsageStats:
        """Return aggregated AI usage stats."""

        return self._get_usage_stats()

    def create_embedding(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        """Create an embedding through the centralized OpenAI client."""

        clean_text = (text or "")[:8000]
        if not clean_text:
            return []
        try:
            response = self._client_instance().embeddings.create(
                model=model,
                input=clean_text,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise self._map_openai_error(exc) from exc
        self._record_usage(tokens_used=0, estimated_cost=Decimal("0"), cache_savings=0)
        self._log_usage(model, 0, False, "embedding")
        return list(response.data[0].embedding)

    def transcribe_audio(self, audio_path: str, language: str = "fr") -> str:
        """Transcribe an audio file using the centralized OpenAI client."""

        try:
            with open(audio_path, "rb") as audio_file:
                result = self._client_instance().audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    timeout=self.timeout,
                )
        except Exception as exc:
            raise self._map_openai_error(exc) from exc
        self._record_usage(tokens_used=0, estimated_cost=Decimal("0"), cache_savings=0)
        self._log_usage("whisper-1", 0, False, "transcription")
        return result.text or ""

    def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        task_type: str = "visa",
        conversation_history: list[ChatMessage] | None = None,
    ) -> str:
        """Compatibility helper for existing code that expects plain text."""

        history = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            history.extend(conversation_history)
        return self.generate_response(user_prompt, task_type, history)["response"]

    def _client_instance(self) -> Any:
        if self._client is None:
            if OpenAI is None:
                raise AIServiceConfigurationError("Le package openai n'est pas disponible.")
            if not self.api_key:
                raise AIServiceConfigurationError("OPENAI_API_KEY n'est pas configurée.")
            self._client = OpenAI(api_key=self.api_key, timeout=self.timeout)
        return self._client

    def _normalize_task_type(self, task_type: str) -> TaskType:
        normalized = (task_type or "visa").strip().lower()
        aliases: Mapping[str, TaskType] = {
            "simple": "faq",
            "question": "faq",
            "standard": "visa",
            "immigration": "visa",
            "coach": "visa",
            "analysis": "analyse",
            "complex": "analyse",
            "dossier": "analyse",
        }
        normalized = aliases.get(normalized, normalized)  # type: ignore[assignment]
        if normalized not in self.ROUTES:
            return "visa"
        return normalized  # type: ignore[return-value]

    def _optimize_history(self, history: list[ChatMessage]) -> list[ChatMessage]:
        clean_history = [
            {"role": item.get("role", ""), "content": item.get("content", "")}
            for item in history
            if item.get("role") in {"system", "user", "assistant"} and item.get("content")
        ]
        if len(clean_history) <= 10:
            return clean_history

        older = clean_history[:-5]
        recent = clean_history[-5:]
        summary = self._summarize_messages(older)
        return [{"role": "system", "content": f"Résumé conversation précédente: {summary}"}] + recent

    def _summarize_messages(self, messages: Iterable[ChatMessage]) -> str:
        joined = " ".join(f"{msg['role']}: {msg['content']}" for msg in messages)
        compact = " ".join(joined.split())
        return compact[:1200] + ("..." if len(compact) > 1200 else "")

    def _lookup_local_faq(self, user_input: str) -> str | None:
        normalized_input = self._normalize_text(user_input)
        for question, answer in self.LOCAL_FAQ.items():
            normalized_question = self._normalize_text(question)
            if normalized_question in normalized_input or normalized_input in normalized_question:
                return answer
        return None

    def _cache_key(
        self,
        user_input: str,
        task_type: TaskType,
        conversation_history: list[ChatMessage],
    ) -> str:
        payload = {
            "input": user_input,
            "task_type": task_type,
            "history": conversation_history,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{self.RESPONSE_CACHE_PREFIX}{digest}"

    def _record_usage(
        self,
        *,
        tokens_used: int,
        estimated_cost: Decimal,
        cache_savings: int,
    ) -> None:
        stats = self._get_usage_stats()
        stats["calls"] += 1
        stats["tokens_consumed"] += tokens_used
        stats["cache_savings"] += cache_savings
        stats["estimated_cost"] = float(Decimal(str(stats["estimated_cost"])) + estimated_cost)
        cache.set(self.USAGE_CACHE_KEY, stats, None)

    def _get_usage_stats(self) -> UsageStats:
        default: UsageStats = {
            "calls": 0,
            "tokens_consumed": 0,
            "cache_savings": 0,
            "estimated_cost": 0.0,
        }
        stats = cache.get(self.USAGE_CACHE_KEY)
        if not isinstance(stats, dict):
            return default
        return {
            "calls": int(stats.get("calls", 0)),
            "tokens_consumed": int(stats.get("tokens_consumed", 0)),
            "cache_savings": int(stats.get("cache_savings", 0)),
            "estimated_cost": float(stats.get("estimated_cost", 0.0)),
        }

    def _estimate_cost(self, model: str, tokens_used: int) -> Decimal:
        per_1k = self.ESTIMATED_COST_PER_1K_TOKENS.get(model, Decimal("0"))
        return (Decimal(tokens_used) / Decimal(1000)) * per_1k

    def _map_openai_error(self, exc: Exception) -> AIServiceError:
        if APITimeoutError is not None and isinstance(exc, APITimeoutError):
            return AIServiceTimeoutError("Timeout lors de l'appel OpenAI.")
        if AuthenticationError is not None and isinstance(exc, AuthenticationError):
            return AIServiceAuthenticationError("Clé OpenAI invalide.")
        if RateLimitError is not None and isinstance(exc, RateLimitError):
            return AIServiceQuotaError("Quota OpenAI dépassé ou limite de débit atteinte.")
        if APIConnectionError is not None and isinstance(exc, APIConnectionError):
            return AIServiceUnavailableError("API OpenAI indisponible.")
        if APIStatusError is not None and isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", None)
            if status_code in {401, 403}:
                return AIServiceAuthenticationError("Clé OpenAI invalide ou non autorisée.")
            if status_code in {429}:
                return AIServiceQuotaError("Quota OpenAI dépassé ou limite de débit atteinte.")
            if status_code and status_code >= 500:
                return AIServiceUnavailableError("API OpenAI temporairement indisponible.")
        if OpenAIError is not None and isinstance(exc, OpenAIError):
            return AIServiceUnavailableError("Erreur OpenAI inattendue.")
        return AIServiceError(str(exc))

    def _log_usage(self, model_used: str, tokens_used: int, cache_hit: bool, task_type: str) -> None:
        logger.info(
            "ai_service_usage",
            extra={
                "model_used": model_used,
                "tokens_used": tokens_used,
                "cache_hit": cache_hit,
                "task_type": task_type,
            },
        )

    def _normalize_text(self, value: str) -> str:
        return " ".join((value or "").lower().replace("’", "'").split()).strip(" ?!.")
