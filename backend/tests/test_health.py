def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "EduVerse" in data["message"]
    assert data["documentation"] == "/docs"
    assert data["health"] == "/health"


def test_top_level_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project"] == "EduVerse"
    assert data["database"] == "connected"
    assert "timestamp" in data


def test_v1_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project"] == "EduVerse"
    assert data["database"] == "connected"


def test_docs_and_openapi_endpoints(client):
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    openapi_data = openapi_resp.json()
    assert openapi_data["info"]["title"] == "EduVerse"

