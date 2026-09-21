# Design Notes

This project is a small agent runtime rather than a collection of prompt templates. The design favors explicit interfaces and observable behavior over maximum model autonomy.

## Core boundaries

The reusable core owns orchestration, retrieval, tool execution, validation, tracing, and model-provider access. Domain adapters own prompts, evidence rules, deterministic routing, tools, and data/API integrations. This keeps the agent loop stable while allowing domains to change independently.

## Deterministic routing around stochastic generation

Some questions have prerequisite evidence that should not depend on prompt compliance. For those query classes, a transparent preflight router executes required tools first. The language model still synthesizes the answer and may request additional tools, but it does not get to skip required evidence.

Examples include fetching current asset state before a calculation, correlating an urgent support ticket with service incidents, and avoiding live tools for document-only questions.

## Evidence discipline

Final answers are checked against retrieved documents and executed tools. The validator rejects unsupported operational identifiers, references to tools that did not run, malformed citation syntax, and domain-specific evidence contamination. Narrow deterministic normalization is used for formatting problems; semantic problems remain visible to the validator.

## Tool contracts

Tool inputs use strict Pydantic schemas. Dependencies and argument bindings are explicit, so a downstream calculation can consume exact values from an authoritative upstream tool rather than model-generated numbers. If a prerequisite tool reports missing data, dependent work stops.

## External integrations

The `service_ops` adapter supports two interchangeable backends:

- `local`: reads the repository's synthetic JSON data directly;
- `http`: calls a JSON REST service through `JsonHttpClient`.

A local mock REST service is included so the HTTP integration path can be exercised without accounts, cloud infrastructure, or external network access. Real adapters can reuse the same boundary with authentication, retries, and organization-specific APIs added outside the agent core.

## Model-provider boundary

The agent depends on a minimal `ChatClient` interface. Ollama is the default provider and runs locally. An optional OpenAI-compatible HTTP client is included to show the provider boundary and can point to local servers such as LM Studio or vLLM. No hosted provider is configured or required.

## Observability and evaluation

Each request records retrieval, routing, tool calls, model output, and validation under a trace ID. Evaluations are deliberately small and inspectable. Standard cases test expected behavior; adversarial cases test missing data, irrelevant evidence, forbidden tools, and tool-chain stopping.

## Cost and privacy posture

The default stack is self-contained and uses synthetic data. It does not require a paid API, hosted vector database, cloud account, telemetry vendor, or external SaaS service. The deterministic CI job runs unit tests only and does not invoke an LLM or any paid endpoint. The local trace format is repository-owned JSONL; no telemetry is exported unless a future adapter is added explicitly.
