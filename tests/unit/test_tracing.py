from shopper.api.tracing import NoopSink, build_sink
from shopper.contracts.chat import ChatResponse


def test_build_sink_noop_without_endpoint():
    sink = build_sink(None)
    assert isinstance(sink, NoopSink)
    sink.record(ChatResponse(response="x", conversation_id="c"))


def test_services_carry_tracer(services):
    assert isinstance(services.tracer, NoopSink)
