## Changelog

### 2026-01-29
- add OpenTelemetry tracing with JSONL file span exporter in `telemetry.py`
- split trace logs into per-trace JSONL files. They are stored now in DEFAULT_TRACE_DIR (if not configured it is /web_agent_traces)
- initialize tracing for each agent run
- add OpenTelemetry dependencies in `pyproject.toml`
- Reorganized code based.
