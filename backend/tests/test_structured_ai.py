from types import SimpleNamespace

import httpx
import pytest
from google.genai.errors import APIError
from pydantic import ValidationError

from app.schemas.ai_learning import GeneratedQuizPayload
from app.services import structured_ai


def _settings(*, provider="gemini", api_key="test-key"):
    return SimpleNamespace(
        AI_PROVIDER=provider,
        AI_API_KEY=api_key,
        AI_MODEL="gemini-3.8-flash",
        AI_TIMEOUT_SECONDS=45,
    )


def test_request_structured_json_uses_gemini_json_configuration(monkeypatch):
    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(text='{"status":"SUCCESS"}')

    def fake_client(**kwargs):
        captured["client"] = kwargs
        return SimpleNamespace(models=FakeModels())

    monkeypatch.setattr(structured_ai, "get_settings", lambda: _settings(provider="openai"))
    monkeypatch.setattr(structured_ai.genai, "Client", fake_client)

    result = structured_ai.request_structured_ai_json(
        "Return a JSON object.",
        {"instruction": "Return success."},
    )

    assert result == {"status": "SUCCESS"}
    assert captured["client"]["api_key"] == "test-key"
    assert captured["client"]["http_options"].timeout == 45_000
    retry_options = captured["client"]["http_options"].retry_options
    assert retry_options.attempts == 3
    assert retry_options.http_status_codes == [408, 429, 500, 502, 503, 504]
    request = captured["request"]
    assert request["model"] == "gemini-3.8-flash"
    assert request["config"].system_instruction == "Return a JSON object."
    assert request["config"].temperature == 0.2
    assert request["config"].response_mime_type == "application/json"


@pytest.mark.parametrize(
    ("code", "provider_status", "exception_type"),
    [
        (401, "UNAUTHENTICATED", structured_ai.AIProviderCredentialsInvalid),
        (403, "PERMISSION_DENIED", structured_ai.AIProviderCredentialsInvalid),
        (429, "RESOURCE_EXHAUSTED", structured_ai.AIProviderRateLimited),
        (503, "UNAVAILABLE", structured_ai.AIProviderError),
    ],
)
def test_gemini_api_errors_are_mapped(code, provider_status, exception_type, monkeypatch):
    def fake_client(**_kwargs):
        def fail(**_request):
            raise APIError(
                code,
                {"error": {"status": provider_status, "message": "provider failure"}},
            )

        return SimpleNamespace(models=SimpleNamespace(generate_content=fail))

    monkeypatch.setattr(structured_ai, "get_settings", _settings)
    monkeypatch.setattr(structured_ai.genai, "Client", fake_client)

    with pytest.raises(exception_type):
        structured_ai.request_structured_ai_json("prompt", {})


def test_gemini_timeout_and_invalid_or_empty_json_are_reported(monkeypatch):
    monkeypatch.setattr(structured_ai, "get_settings", _settings)

    def timeout_client(**_kwargs):
        def fail(**_request):
            raise httpx.ReadTimeout("request timeout")

        return SimpleNamespace(models=SimpleNamespace(generate_content=fail))

    monkeypatch.setattr(structured_ai.genai, "Client", timeout_client)
    with pytest.raises(structured_ai.AIProviderError, match="timed out"):
        structured_ai.request_structured_ai_json("prompt", {})

    def deadline_client(**_kwargs):
        def fail(**_request):
            raise APIError(
                504,
                {"error": {"status": "DEADLINE_EXCEEDED", "message": "deadline"}},
            )

        return SimpleNamespace(models=SimpleNamespace(generate_content=fail))

    monkeypatch.setattr(structured_ai.genai, "Client", deadline_client)
    with pytest.raises(structured_ai.AIProviderError, match="timed out"):
        structured_ai.request_structured_ai_json("prompt", {})

    for text, expected_message in (
        ("not JSON", "invalid JSON"),
        ("", "empty response"),
        ("[]", "invalid response"),
    ):
        monkeypatch.setattr(
            structured_ai.genai,
            "Client",
            lambda **_kwargs: SimpleNamespace(
                models=SimpleNamespace(
                    generate_content=lambda **_request: SimpleNamespace(text=text)
                )
            ),
        )
        with pytest.raises(structured_ai.AIProviderError, match=expected_message):
            structured_ai.request_structured_ai_json("prompt", {})


def test_missing_key_and_unsupported_provider_fail_clearly(monkeypatch):
    monkeypatch.setattr(
        structured_ai,
        "get_settings",
        lambda: _settings(provider="gemini", api_key=" "),
    )
    with pytest.raises(structured_ai.AIProviderNotConfigured, match="AI_API_KEY"):
        structured_ai.request_structured_ai_json("prompt", {})

    monkeypatch.setattr(
        structured_ai,
        "get_settings",
        lambda: _settings(provider="other"),
    )
    with pytest.raises(structured_ai.AIProviderNotConfigured, match="AI_PROVIDER"):
        structured_ai.request_structured_ai_json("prompt", {})


def test_generated_quiz_accepts_gemini_string_options():
    quiz = GeneratedQuizPayload.model_validate(
        {
            "questions": [
                {
                    "question": "Which option is supported by the lesson?",
                    "question_type": "mcq",
                    "options": ["Supported answer", "Incorrect answer"],
                    "correct_answer": "Supported answer",
                    "explanation": "The lesson supports this answer.",
                    "difficulty": "medium",
                }
            ]
        }
    )

    assert [option.text for option in quiz.questions[0].options] == [
        "Supported answer",
        "Incorrect answer",
    ]
    with pytest.raises(ValidationError):
        GeneratedQuizPayload.model_validate(
            {
                "questions": [
                    {
                        "question": "Which option is supported by the lesson?",
                        "question_type": "mcq",
                        "options": [3],
                        "correct_answer": "Supported answer",
                        "explanation": "The lesson supports this answer.",
                        "difficulty": "medium",
                    }
                ]
            }
        )
