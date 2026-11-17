import json
import logging

import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import get_settings


logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    pass


class AIProviderNotConfigured(Exception):
    pass


class AIProviderCredentialsInvalid(AIProviderError):
    pass


class AIProviderRateLimited(AIProviderError):
    pass


def request_structured_ai_json(system_prompt: str, user_payload: dict) -> dict:
    settings = get_settings()
    provider = settings.AI_PROVIDER.strip().lower()
    if provider not in {"gemini", "google", "openai"}:
        raise AIProviderNotConfigured(
            "AI_PROVIDER must be set to 'gemini' to use Google Gemini for AI learning tools."
        )
    if provider == "openai":
        logger.info("Using Google Gemini with the legacy AI_PROVIDER=openai setting; update it to gemini.")
    if not settings.AI_API_KEY.strip():
        raise AIProviderNotConfigured(
            "The backend AI_API_KEY is missing. Add your Google Gemini API key to backend/.env and restart the backend."
        )

    client = genai.Client(
        api_key=settings.AI_API_KEY.strip(),
        http_options=types.HttpOptions(
            timeout=max(1, settings.AI_TIMEOUT_SECONDS) * 1000,
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=1.0,
                max_delay=4.0,
                exp_base=2.0,
                jitter=0.1,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            ),
        ),
    )
    try:
        response = client.models.generate_content(
            model=settings.AI_MODEL,
            contents=json.dumps(user_payload, ensure_ascii=False),
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
    except APIError as exc:
        code = getattr(exc, "code", None)
        provider_status = getattr(exc, "status", None)
        if code in (401, 403) or provider_status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
            logger.warning("Google Gemini rejected the configured credentials or API access (status %s).", code)
            raise AIProviderCredentialsInvalid(
                "Google Gemini rejected the configured API key or API access. Check AI_API_KEY and Gemini API access in backend/.env."
            ) from exc
        if code == 429 or provider_status == "RESOURCE_EXHAUSTED":
            logger.warning("Google Gemini quota or rate limit reached.")
            raise AIProviderRateLimited(
                "Google Gemini quota or rate limit reached. Check your Google AI Studio usage and try again later."
            ) from exc
        if code == 504 or provider_status == "DEADLINE_EXCEEDED":
            logger.warning("Google Gemini exceeded its request deadline.")
            raise AIProviderError(
                "Google Gemini's generation service timed out (504). Retry later or verify that AI_MODEL supports generateContent."
            ) from exc
        if code == 503 or provider_status == "UNAVAILABLE":
            logger.warning("Google Gemini service is temporarily unavailable.")
            raise AIProviderError("Google Gemini is temporarily unavailable. Please try again later.") from exc
        logger.error("Google Gemini returned API status %s.", code)
        if code == 404:
            raise AIProviderError(
                "The configured Google Gemini model was not found. Check AI_MODEL in backend/.env."
            ) from exc
        raise AIProviderError(
            f"Google Gemini could not complete the request (API status {code or 'unknown'}). Please try again."
        ) from exc
    except (httpx.TimeoutException, TimeoutError) as exc:
        logger.warning("Google Gemini request timed out.")
        raise AIProviderError(
            "Google Gemini timed out. Check your connection and AI_TIMEOUT_SECONDS, then try again."
        ) from exc
    except (httpx.RequestError, ConnectionError, OSError) as exc:
        logger.warning("Google Gemini could not be reached.")
        raise AIProviderError(
            "Google Gemini is currently unreachable. Check your connection and try again."
        ) from exc

    try:
        content = response.text
    except (AttributeError, ValueError) as exc:
        logger.warning("Google Gemini returned no usable text content.")
        raise AIProviderError("Google Gemini returned an empty response. Please try again.") from exc
    if not isinstance(content, str) or not content.strip():
        logger.warning("Google Gemini returned an empty structured response.")
        raise AIProviderError("Google Gemini returned an empty response. Please try again.")
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("Google Gemini returned invalid JSON.")
        raise AIProviderError("Google Gemini returned invalid JSON. Please try again.") from exc
    if not isinstance(result, dict):
        raise AIProviderError("Google Gemini returned an invalid response. Please try again.")
    return result
