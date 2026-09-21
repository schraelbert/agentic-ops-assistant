import pytest

from app.llm import OllamaClient, OpenAICompatibleClient, create_llm_client


def test_default_provider_is_ollama(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert isinstance(create_llm_client(), OllamaClient)


def test_openai_compatible_provider_can_be_local(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "http://localhost:1234/v1")
    client = create_llm_client()
    assert isinstance(client, OpenAICompatibleClient)
    assert client.base_url == "http://localhost:1234/v1"


def test_unknown_provider_rejected():
    with pytest.raises(ValueError):
        create_llm_client("not-a-provider")


def test_remote_openai_compatible_endpoint_blocked_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_REMOTE_LLM", raising=False)
    with pytest.raises(ValueError, match="Remote OpenAI-compatible endpoints are disabled"):
        OpenAICompatibleClient(base_url="https://api.example.com/v1")


def test_remote_openai_compatible_endpoint_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("ALLOW_REMOTE_LLM", "1")
    client = OpenAICompatibleClient(base_url="https://api.example.com/v1")
    assert client.base_url == "https://api.example.com/v1"


def test_remote_ollama_endpoint_blocked_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_REMOTE_LLM", raising=False)
    with pytest.raises(ValueError, match="Remote LLM endpoints are disabled"):
        OllamaClient(base_url="https://ollama.example.com")
