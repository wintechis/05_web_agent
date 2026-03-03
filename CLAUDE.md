# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Package manager**: `uv`

```bash
# Install dependencies
uv sync

# Run HTTP server
python -m agent.server
# or: uvicorn agent.server:app --host 0.0.0.0 --port 8000

# Run inference on benchmark questions
python -m benchmark.cli.run_inference <input_folder> <output_folder>
MAX_AGENT_STEPS=10 python -m benchmark.cli.run_inference evaluation/experiments/02/questions evaluation/experiments/02

# Run evaluation on inference results
python -m benchmark.cli.run_evaluation <results.yaml> [--output metrics.yaml]

# Generate Wikipedia/DBpedia path-finding challenges
python -m benchmark.cli.generate_challenge [--distance 3] [--number-of-challenges 10]

# Hydra-based inference (switches models/experiments without editing .env)
python run_inference_hydra.py experiment=semantic_outgoing_turtle model=llama_3_3_70b
# Multirun across experiments:
python run_inference_hydra.py -m experiment=exp1,exp2,exp3
```

No test suite is configured.

## Architecture

The project is a web-navigating agent benchmarked on graph path-finding tasks (Wikipedia/DBpedia). Two subsystems:

### 1. Agent (`agent/`)

`vanilla_web_agent` in `agent/__init__.py` creates a `RationaleToolCallingAgent` (from `agents.py`) — a subclass of smolagents' `ToolCallingAgent` that requires explicit reasoning before each tool call.

**Tools** (`tools.py`): `GET`, `POST`, `PUT`, `POST_RDF`, `StructuredFinalAnswer`. The GET tool is the most complex — it fetches a URI and applies resource transformation before returning content to the agent.

**Resource transformation** (`resource_transform.py`): Driven entirely by env vars, this pipeline rewrites URIs (Wikipedia ↔ DBpedia), prunes RDF graphs (outgoing-only or in-and-outgoing), and serializes to the configured format (wikitext, HTML, JSON-LD, Turtle variants). Applied inside the GET tool before content is returned to the LLM.

**Context compression** (`context_compression.py`): Truncates tool response messages when total token count exceeds `MAX_TOKEN_FOR_MODEL * 0.8`.

**Server** (`server.py`): FastAPI with async background tasks. `POST /ask` returns an ID immediately; `GET /ask/{id}` polls for `pending`/`completed`/`failed`.

**Telemetry** (`telemetry.py`): OpenTelemetry tracing with a custom JSONL span exporter. Each inference run writes per-trace `.jsonl` files to `OTEL_TRACE_DIR`.

### 2. Benchmark (`benchmark/`)

Layered as domain / application / infrastructure / CLI:

- **Domain** (`domain/`): `Path`, `TaskEntry`, `TaskResult`, `EvaluationMetrics` models; `MetricsCalculator` for CSR/TSR/PO/PPM; `EdgeValidator` checking if consecutive URIs are linked via HTTP.
- **Application** (`application/`): `RunInferenceUseCase` runs the agent on every YAML question; `RunEvaluationUseCase` computes metrics; `WikipediaChallengeGenerator` creates challenges via SPARQL.
- **Infrastructure** (`infrastructure/`): YAML I/O helpers and URI link-checking.
- **CLI** (`cli/`): Thin wrappers over application use cases.

**Metrics**:
- **CSR** – Claimed Success Rate: % tasks where agent returns a non-empty answer
- **TSR** – True Success Rate: % where predicted path ends at target AND all edges are valid
- **PO** – Path Optimality: avg(gold_length / predicted_length)
- **PPM** – Path Prefix Match: % of gold edges matching the common prefix

### 3. Configuration (`config/`)

Hydra configs control three axes:
- **`experiment/`** – 18 variants combining noise type, RDF representation, and compression
- **`model/`** – LLM choices (qwen3_coder_30b, llama_3_3_70b, devstral_2_123b, etc.)
- **`datasource/`** – Dataset paths (default: `experiment_10` with 10 DBpedia + 10 Wikipedia questions)

## Environment Variables

Copy `.env.example` to `.env`. Key variables:

| Variable | Purpose |
|----------|---------|
| `OPENAI_MODEL_ID`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` | LLM backend (OpenAI-compatible) |
| `MODIFY_CONTEXT` | Enable resource transformation in GET tool |
| `REPRESENTATION_FORMAT` | `wikitext` or `rdf` |
| `RDF_REPRESENTATION` | `html`, `json-ld`, `turtle`, `turtle-compact`, `turtle-terser` |
| `PRUNING_METHOD` | `unpruned`, `outgoing-only`, `in-and-outgoing` |
| `CONTEXT_COMPRESSION` | Truncate tool messages when near token limit |
| `MAX_TOKEN_FOR_MODEL` | Token budget (default 120000) |
| `MAX_AGENT_STEPS` | Cap agent steps per question |
| `OTEL_TRACE_DIR` | Output directory for JSONL trace files |
