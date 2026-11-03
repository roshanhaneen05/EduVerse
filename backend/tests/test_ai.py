from unittest.mock import patch
import pytest
from app.database import SessionLocal
from app.models.ai import AIConversation, AIMessage
from app.services.ai_service import demo_provider


def get_auth_headers(client, email="alex.rivera@eduverse.io", password="EduVerseDemo2026!"):
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_ai_conversation_creation(client):
    headers = get_auth_headers(client, email="alex.rivera@eduverse.io")
    payload = {"message": "Explain FastAPI and dependency injection"}
    response = client.post("/api/v1/ai/chat", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    assert data["conversation_id"] > 0
    assert "message" in data
    assert len(data["message"]) > 0
    assert "FastAPI" in data["message"]


def test_ai_multi_turn_persistence(client):
    headers = get_auth_headers(client, email="alex.rivera@eduverse.io")

    # Turn 1
    resp1 = client.post(
        "/api/v1/ai/chat",
        json={"message": "What is Python FastAPI?"},
        headers=headers,
    )
    assert resp1.status_code == 200
    conv_id = resp1.json()["conversation_id"]

    # Turn 2
    resp2 = client.post(
        "/api/v1/ai/chat",
        json={"message": "Show me a code example", "conversation_id": conv_id},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["conversation_id"] == conv_id

    # Retrieve history and verify 4 messages (user, assistant, user, assistant)
    detail_resp = client.get(f"/api/v1/ai/conversations/{conv_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == conv_id
    messages = detail["messages"]
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert "Python FastAPI" in messages[0]["content"]
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert "code example" in messages[2]["content"]
    assert messages[3]["role"] == "assistant"


def test_ai_conversation_history_retrieval(client):
    headers = get_auth_headers(client, email="alex.rivera@eduverse.io")
    resp = client.get("/api/v1/ai/conversations", headers=headers)
    assert resp.status_code == 200
    conversations = resp.json()
    assert isinstance(conversations, list)
    assert len(conversations) >= 1
    assert "message_count" in conversations[0]
    assert conversations[0]["message_count"] >= 2


def test_ai_unauthorized_access_prevented(client):
    headers_alex = get_auth_headers(client, email="alex.rivera@eduverse.io")
    headers_priya = get_auth_headers(client, email="priya.patel@eduverse.io")

    # Alex creates a conversation
    resp = client.post(
        "/api/v1/ai/chat",
        json={"message": "Confidential research on system architecture"},
        headers=headers_alex,
    )
    conv_id = resp.json()["conversation_id"]

    # Priya attempts to read Alex's conversation
    forbidden_get = client.get(f"/api/v1/ai/conversations/{conv_id}", headers=headers_priya)
    assert forbidden_get.status_code == 403

    # Priya attempts to send a message to Alex's conversation
    forbidden_post = client.post(
        "/api/v1/ai/chat",
        json={"message": "Injected message", "conversation_id": conv_id},
        headers=headers_priya,
    )
    assert forbidden_post.status_code == 403

    # Priya attempts to delete Alex's conversation
    forbidden_delete = client.delete(f"/api/v1/ai/conversations/{conv_id}", headers=headers_priya)
    assert forbidden_delete.status_code == 403


def test_ai_invalid_conversation_id(client):
    headers = get_auth_headers(client, email="alex.rivera@eduverse.io")

    # Non-existent ID for retrieval
    get_resp = client.get("/api/v1/ai/conversations/999999", headers=headers)
    assert get_resp.status_code == 404

    # Non-existent ID for posting
    post_resp = client.post(
        "/api/v1/ai/chat",
        json={"message": "Hello", "conversation_id": 999999},
        headers=headers,
    )
    assert post_resp.status_code == 404


def test_ai_provider_failure_handling(client):
    headers = get_auth_headers(client, email="alex.rivera@eduverse.io")

    # Mock provider failure
    with patch.object(demo_provider, "generate_response", side_effect=RuntimeError("AI Provider Service Unavailable")):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"message": "Will this crash if provider fails?"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "issue processing your query" in data["message"].lower()

        # Verify user message and error fallback were still persisted without crashing
        conv_id = data["conversation_id"]
        detail = client.get(f"/api/v1/ai/conversations/{conv_id}", headers=headers).json()
        assert len(detail["messages"]) == 2
        assert detail["messages"][0]["role"] == "user"
        assert detail["messages"][1]["role"] == "assistant"


def test_ai_database_persistence():
    db = SessionLocal()
    try:
        conversations = db.query(AIConversation).all()
        assert len(conversations) >= 1
        for c in conversations:
            assert c.user_id is not None
            assert c.title is not None
            # Check messages are relational
            msgs = db.query(AIMessage).filter(AIMessage.conversation_id == c.id).all()
            assert len(msgs) >= 1
            for m in msgs:
                assert m.role in ("user", "assistant", "system")
                assert len(m.content) > 0
    finally:
        db.close()

