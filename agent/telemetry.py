import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from openinference.instrumentation.openai import OpenAIInstrumentor

DEFAULT_SERVICE_NAME = "web-agent"
DEFAULT_TRACE_DIR = "web_agent_traces"
TRACE_DIR_ENV = "OTEL_TRACE_DIR"

_TRACING_INITIALIZED = False


def _format_timestamp(nanoseconds: int | None) -> str | None:
    if nanoseconds is None:
        return None
    return datetime.fromtimestamp(nanoseconds / 1e9, tz=timezone.utc).isoformat()


@dataclass
class JSONFileSpanExporter(SpanExporter):
    output_dir: str

    def export(self, spans: Iterable[ReadableSpan]) -> SpanExportResult:
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            for span in spans:
                trace_id = format(span.context.trace_id, "032x")
                output_path = os.path.join(self.output_dir, f"{trace_id}.jsonl")
                parent_span_id = (
                    format(span.parent.span_id, "016x") if span.parent else None
                )
                status = span.status
                trace_data = {
                    "trace_id": trace_id,
                    "span_id": format(span.context.span_id, "016x"),
                    "parent_span_id": parent_span_id,
                    "name": span.name,
                    "start_time": _format_timestamp(span.start_time),
                    "end_time": _format_timestamp(span.end_time),
                    "duration_ms": (
                        (span.end_time - span.start_time) / 1e6
                        if span.end_time
                        else None
                    ),
                    "attributes": dict(span.attributes) if span.attributes else {},
                    "events": [
                        {
                            "name": event.name,
                            "timestamp": _format_timestamp(event.timestamp),
                            "attributes": (
                                dict(event.attributes) if event.attributes else {}
                            ),
                        }
                        for event in span.events
                    ],
                    "status": {
                        "code": status.status_code.name if status else None,
                        "description": status.description if status else None,
                    },
                }
                with open(output_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(trace_data, ensure_ascii=False) + "\n")
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        finalize_traces(self.output_dir)


def finalize_traces(trace_dir: str) -> None:
    """Convert all .jsonl trace files in trace_dir to .json with indent=4."""
    if not os.path.isdir(trace_dir):
        return
    for filename in os.listdir(trace_dir):
        if not filename.endswith(".jsonl"):
            continue
        jsonl_path = os.path.join(trace_dir, filename)
        json_path = os.path.join(trace_dir, filename[:-1])  # .jsonl -> .json
        spans = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    spans.append(json.loads(line))
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(spans, f, indent=4, ensure_ascii=False)
        os.remove(jsonl_path)


def init_tracing() -> None:
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    trace_dir = os.getenv(TRACE_DIR_ENV, DEFAULT_TRACE_DIR)
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(JSONFileSpanExporter(trace_dir))
    )
    trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument()

    _TRACING_INITIALIZED = True
