"""Optional OpenTelemetry export of per-stage timings. No-op unless the ``otel`` extra is
installed and ``SHOPPER_OTEL_ENDPOINT`` is set."""

from __future__ import annotations

from typing import Any, Protocol

from shopper.contracts.chat import ChatResponse


class TraceSink(Protocol):
    def record(self, response: ChatResponse) -> None: ...


class NoopSink:
    def record(self, response: ChatResponse) -> None:
        return None


class OTelSink:
    def __init__(self, endpoint: str, service_name: str = "personal-shopper"):
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("shopper")

    def record(self, response: ChatResponse) -> None:
        meta: dict[str, Any] = response.metadata
        with self._tracer.start_as_current_span("chat") as root:
            root.set_attribute("llm_calls", int(meta.get("llm_calls", 0)))
            root.set_attribute("from_cache", bool(meta.get("from_cache", False)))
            root.set_attribute("data_count", response.data_count)
            for ev in meta.get("stages", []):
                with self._tracer.start_as_current_span(str(ev["stage"])) as span:
                    span.set_attribute("ms", int(ev["ms"]))


def build_sink(endpoint: str | None) -> TraceSink:
    if not endpoint:
        return NoopSink()
    return OTelSink(endpoint)
