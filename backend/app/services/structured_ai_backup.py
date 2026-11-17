import json
import logging

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from app.config import get_settings


logger = logging.getLogger(__name__)


class AIProviderNotConfigured(Exception):
    pass


class AIProviderCredentialsInvalid(Exception):
    pass


class AIProviderRateLimited(Exception):
    pass


class AIProviderError(Exception):
    pass


def request_structured_ai_json(system_prompt: str, user_payload: dict) -> dict:
    settings = get_settings()
    if settings.AI_PROVIDER.strip().lower() != "openai":
        raise AIProviderNotConfigured(
            "AI_PROVIDER is not set to 'openai'. Configure the backend AI settings to generate quizzes."
        )
    if not settings.AI_API_KEY.strip():
        raise AIProviderNotConfigured(
            "The backend AI_API_KEY is missing. Add your OpenAI API key to backend/.env and restart the backend."
        )

    client = OpenAI(
        api_key=settings.AI_API_KEY.strip(),
        base_url=settings.AI_API_BASE_URL.rstrip("/"),
        timeout=settings.AI_TIMEOUT_SECONDS,
        max_retries=0,
    )
    try:
        response = client.chat.completions.create(
            model=settings.AI_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
        )
    except AuthenticationError as exc:
        logger.warning("OpenAI rejected the configured API key.")
        raise AIProviderCredentialsInvalid(
            "OpenAI rejected the configured API key. Check AI_API_KEY in backend/.env and restart the backend."
        ) from exc
    except PermissionDeniedError as exc:
        logger.warning("OpenAI denied the configured model or project access.")
        raise AIProviderError(
            "OpenAI denied access. Check that the configured key and model are enabled for your project."
        ) from exc
    except RateLimitError as exc:
        logger.warning("OpenAI rate limit or quota reached.")
        raise AIProviderRateLimited(
            "OpenAI rate limit or quota reached. Check your API usage and try again later."
        ) from exc
    except (APITimeoutError, APIConnectionError) as exc:
        logger.warning("OpenAI request failed due to a connection or timeout error.")
        raise AIProviderError("OpenAI is currently unreachable. Check your connection and try again.") from exc
    except APIStatusError as exc:
        logger.error("OpenAI returned HTTP status %s.", exc.status_code)
        if exc.status_code == 404:
            raise AIProviderError(
                "The configured OpenAI model was not found. Check AI_MODEL in backend/.env."
            ) from exc
        raise AIProviderError(
            f"OpenAI could not complete the request (HTTP {exc.status_code}). Please try again."
        ) from exc

    try:
        content = response.choices[0].message.content
        result = json.loads(content or "")
    except (IndexError, TypeError, json.JSONDecodeError) as exc:
        logger.error("OpenAI returned invalid structured content.")
        raise AIProviderError("OpenAI returned an invalid response. Please try again.") from exc
    if not isinstance(result, dict):
        raise AIProviderError("OpenAI returned an invalid response. Please try again.")
    return result
