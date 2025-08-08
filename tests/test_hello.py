import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200

def test_process_audio():
    response = client.post("/process_audio", files={"file": ("test.wav", b"test audio data")})
    assert response.status_code == 200
    assert "result" in response.json()