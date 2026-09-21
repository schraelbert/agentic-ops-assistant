from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import AgenticOpsAssistant
from .domain_registry import DOMAINS
from .trace import get_trace, list_recent_traces

app = FastAPI(title="Agentic Ops Assistant", version="0.11.2")
_agents: dict[str, AgenticOpsAssistant] = {}
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    domain: str = "renewable_ops"


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "domains": [
            {
                "name": name,
                "display_name": domain["display_name"],
                "description": domain["description"],
            }
            for name, domain in sorted(DOMAINS.items())
        ],
    }


@app.post("/ask")
def ask(req: AskRequest):
    if req.domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"Unknown domain: {req.domain}")
    if req.domain not in _agents:
        _agents[req.domain] = AgenticOpsAssistant(req.domain)
    return _agents[req.domain].ask(req.question)


@app.get("/traces/recent")
def recent_traces(limit: int = 20):
    return {"traces": list_recent_traces(limit)}


@app.get("/trace/{trace_id}")
def trace(trace_id: str):
    events = get_trace(trace_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")
    return {"trace_id": trace_id, "events": events}
