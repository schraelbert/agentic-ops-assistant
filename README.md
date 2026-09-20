# Agentic Ops Assistant

A compact, production-minded agentic AI project that combines retrieval-augmented generation (RAG), structured tool calling, execution traces, evaluation, APIs, and Docker.

The repository is intentionally **domain-agnostic at the core**. The included demo domain uses synthetic renewable-energy asset data, but domain prompts, documents, data, and tools live behind a small adapter so additional domains can be added without rewriting the agent loop.

## What this demonstrates

- local LLM orchestration with Ollama;
- embedding-based retrieval over domain documents;
- structured tool selection and multi-step tool use;
- deterministic preflight routing for prerequisite evidence on safety- or reliability-sensitive query classes;
- separation between the reusable agent core and domain-specific tools/data;
- grounded answers that distinguish retrieved procedures from live-style tool data;
- structured JSONL traces plus a `/trace/{trace_id}` inspection endpoint;
- a small transparent evaluation suite with pass rate, evidence checks, and latency;
- FastAPI and containerized deployment.

## Included demo domain: Renewable Asset Operations

The sample domain uses synthetic wind-turbine data. Example questions include:

- `WTG-02 is underperforming. What should the operator check first?`
- `What is the approximate current capacity factor of WTG-01?`
- `What does the procedure say when gearbox bearing temperature stays above 80 C after load reduction?`

The agent can retrieve operating procedures, query synthetic asset state and alarms, and calculate simple metrics before producing a grounded response.

## Architecture

```text
Client -> FastAPI /ask
             |
             v
      AgenticOpsAssistant
       /      |       \
      v       v        v
Embedding RAG  Router   Domain tools
(document facts)  (current facts/actions)
       \             /
        v           v
          Local LLM
             |
             v
     answer + tool calls + trace
```

Domain-specific pieces are isolated under `domains/`:

```text
agentic-ops-assistant/
├── app/                     # reusable agent core
│   ├── agent.py
│   ├── domain_registry.py
│   ├── llm.py
│   ├── main.py
│   ├── retrieval.py
│   └── trace.py
├── domains/
│   └── renewable_ops/       # example domain adapter
│       ├── domain.py
│       ├── routing.py
│       ├── tools.py
│       └── data/
├── evals/
├── tests/
├── Dockerfile
└── docker-compose.yml
```

## Quick start

The default setup is fully containerized: the API and Ollama run as separate services on the same Docker network. A one-shot `model-init` service pulls the configured model into a persistent Ollama volume.

### 1. Start the stack

```bash
cp .env.example .env
docker compose up --build
```

On the first run, Docker will pull the Ollama image, build the API image, download the configured LLM (default: `qwen2.5:7b`), and cache the embedding model. Later starts reuse the named volumes.

Check status:

```bash
docker compose ps
```

The API is available at `http://localhost:8000`. Ollama is intentionally **not exposed to the host** in the default stack; the API reaches it over the internal Compose network at `http://ollama:11434`.

### 2. Ask a question

```bash
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"domain":"renewable_ops","question":"WTG-02 is underperforming. What should the operator check first?"}'
```

Health check:

```bash
curl http://localhost:8000/health
```

### 3. Inspect traces

Structured events are written to the host-mounted `traces/` directory:

```bash
tail -f traces/traces.jsonl
```

### Model selection

Set a different Ollama model in `.env`:

```text
OLLAMA_MODEL=qwen2.5:7b
```

Then restart the stack. The `model-init` service will pull the selected model if it is not already present in the project volume.

### Optional: reuse an Ollama already running on the host

For local development, if Ollama is already exposed on host port `11434`, you can avoid running a second Ollama container:

```bash
docker compose -f docker-compose.external-ollama.yml up --build
```

That mode points the API container to `host.docker.internal:11434`. The default `docker-compose.yml` remains the reproducible, self-contained setup intended for the public repository.

### Stop the stack

```bash
docker compose down
```

To also delete downloaded model/cache volumes:

```bash
docker compose down -v
```

## Trace inspection

Every `/ask` response includes a `trace_id`. Inspect the full execution path through the API:

```bash
curl http://localhost:8000/trace/<trace_id>
```

The response includes retrieval events, model outputs, and tool calls in order. Raw JSONL traces are also written to `traces/traces.jsonl`.

## Evaluation

Run the transparent evaluation suite inside the API container:

```bash
docker-compose -f docker-compose.external-ollama.yml exec api python -m evals.run_evals
```

Or in the fully self-contained stack:

```bash
docker compose exec api python -m evals.run_evals
```

The runner writes `evals/latest_report.json` and reports per-case tool usage, key answer terms, expected evidence references, simple unsupported-claim checks, latency, and an overall pass rate. The suite is intentionally small and inspectable rather than pretending to be a complete agent benchmark.

## Reliability choices

- Current operational facts come from tools rather than model memory.
- Procedures come from retrieved local documents.
- Domain adapters define their own safety and evidence rules.
- Deterministic preflight routing guarantees prerequisite evidence for selected query classes instead of relying on prompt compliance alone.
- Tool calls are deterministic Python functions with explicit inputs.
- Tool dependencies and selected arguments can be validated against prior authoritative tool results before execution.
- Planned calculation inputs can be bound directly to fields from authoritative prior tool results.
- Final-answer validation catches leaked tool-call syntax and asks the model for a clean rewrite.
- Retrievals, model outputs, and tool calls are logged with trace IDs.
- The repository uses synthetic data only.

## Adding another domain

A new domain only needs:

1. a system prompt and document path;
2. a set of tool specifications;
3. domain data or API adapters;
4. registration in `app/domain_registry.py`.

For example, the same core can support internal business operations, customer support, asset maintenance, or workflow automation without changing the orchestration loop.

## Roadmap

- add a second non-energy domain to prove portability;
- add pgvector or Qdrant as an optional vector backend;
- add tool schemas with Pydantic validation;
- add role-based or specialist-agent handoffs only where they improve task quality;
- add OpenTelemetry-compatible traces, latency, and token/cost metrics;
- add adversarial evaluations for missing data, conflicting evidence, and unsafe requests;
- add a small web UI for interactive demos.

## Why this project exists

The goal is to demonstrate a reusable engineering pattern for practical agentic systems: retrieve evidence, call deterministic tools, keep traces, evaluate behavior, and make domain assumptions explicit.

It is deliberately small enough to understand end to end, while leaving clear paths toward production concerns such as observability, access control, vector databases, and richer evaluation.


## Inspect recent traces

List trace IDs that are actually present in the persisted JSONL trace store:

```bash
curl 'http://localhost:8000/traces/recent?limit=10'
```

Then inspect one execution:

```bash
curl http://localhost:8000/trace/<trace_id>
```

Trace IDs from containers that ran before the host trace volume was mounted are not recoverable.

## Evaluation semantics

The eval suite uses both a weighted score and hard gates. A case only passes when required tools, required evidence references, and unsupported-claim checks all pass. This prevents a fluent answer from passing while skipping required operational evidence or deterministic tools.

## Deterministic preflight routing

The renewable demo intentionally uses a small rule-based preflight planner for query classes where missing a prerequisite tool would make the answer unreliable. For example, underperformance triage forces a recent-alarm lookup, while current capacity-factor questions force asset status followed by a deterministic calculation using values bound from that status result. Procedure-only questions bypass operational tools and stay grounded in retrieved documentation. The LLM still performs synthesis and may request additional tools, but prerequisite evidence is not left to prompt compliance alone.
