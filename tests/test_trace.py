import json

from app import trace as trace_module


def test_get_trace_filters_by_trace_id(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    rows = [
        {"ts": "1", "trace_id": "abc", "event_type": "retrieval", "payload": {}},
        {"ts": "2", "trace_id": "xyz", "event_type": "tool", "payload": {}},
        {"ts": "3", "trace_id": "abc", "event_type": "model", "payload": {}},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(trace_module, "TRACE_PATH", path)

    events = trace_module.get_trace("abc")

    assert [event["event_type"] for event in events] == ["retrieval", "model"]


def test_get_trace_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(trace_module, "TRACE_PATH", tmp_path / "missing.jsonl")
    assert trace_module.get_trace("abc") == []


def test_list_recent_traces(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    rows = [
        {"ts": "2026-01-01T00:00:00+00:00", "trace_id": "old", "event_type": "retrieval", "payload": {}},
        {"ts": "2026-01-01T00:00:01+00:00", "trace_id": "new", "event_type": "retrieval", "payload": {}},
        {"ts": "2026-01-01T00:00:02+00:00", "trace_id": "new", "event_type": "tool", "payload": {}},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(trace_module, "TRACE_PATH", path)

    traces = trace_module.list_recent_traces(10)

    assert traces[0]["trace_id"] == "new"
    assert traces[0]["event_count"] == 2
    assert traces[0]["event_types"] == ["retrieval", "tool"]
