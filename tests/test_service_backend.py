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
