from app.adapters.http_json import JsonHttpClient


def test_http_client_requires_http_scheme():
    try:
        JsonHttpClient("localhost:8090")
    except ValueError as exc:
        assert "http://" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_http_client_builds_request(monkeypatch):
    seen = {}

    class Response:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {"ok": True}

    def fake_get(url, params=None, timeout=None):
        seen.update(url=url, params=params, timeout=timeout)
        return Response()

    monkeypatch.setattr("app.adapters.http_json.requests.get", fake_get)
    result = JsonHttpClient("http://mock-service:8090", timeout_s=3).get(
        "/incidents", params={"service_id": "SYNC-API"}
    )
    assert result == {"ok": True}
    assert seen == {
        "url": "http://mock-service:8090/incidents",
        "params": {"service_id": "SYNC-API"},
        "timeout": 3,
    }
