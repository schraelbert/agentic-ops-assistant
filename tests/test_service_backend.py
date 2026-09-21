from domains.service_ops import backend


def test_local_backend_remains_default(monkeypatch):
    monkeypatch.delenv("SERVICE_OPS_BACKEND", raising=False)
    assert backend.backend_mode() == "local"
    assert backend.ticket("TCK-101")["ticket_id"] == "TCK-101"


def test_http_backend_delegates(monkeypatch):
    monkeypatch.setenv("SERVICE_OPS_BACKEND", "http")

    class FakeClient:
        def get(self, path, params=None):
            return {"path": path, "params": params}

    monkeypatch.setattr(backend, "_http", lambda: FakeClient())
    assert backend.ticket("TCK-101") == {"path": "tickets/TCK-101", "params": None}
    assert backend.incidents("SYNC-API", 2) == {
        "path": "incidents",
        "params": {"service_id": "SYNC-API", "limit": 2},
    }


def test_remote_service_backend_blocked_by_default(monkeypatch):
    monkeypatch.setenv("SERVICE_OPS_BASE_URL", "https://service.example.com")
    monkeypatch.delenv("ALLOW_REMOTE_SERVICE_OPS", raising=False)
    try:
        backend._http()
    except ValueError as exc:
        assert "Remote service_ops endpoints are disabled" in str(exc)
    else:
        raise AssertionError("remote backend should require explicit opt-in")


def test_remote_service_backend_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("SERVICE_OPS_BASE_URL", "https://service.example.com")
    monkeypatch.setenv("ALLOW_REMOTE_SERVICE_OPS", "1")
    client = backend._http()
    assert client.base_url == "https://service.example.com"
