"""Métricas sem identificadores de alta cardinalidade e tracing opcional."""

import json
import logging
import os
import time
from contextlib import AbstractContextManager, contextmanager, nullcontext

from prometheus_client import CollectorRegistry, Counter, Histogram

registry = CollectorRegistry()
requests_total = Counter(
    "otm_http_requests_total", "Requisições por método e código", ["method", "status"], registry=registry
)
latency = Histogram("otm_http_duration_seconds", "Duração HTTP", ["method"], registry=registry)
jobs_total = Counter("otm_jobs_total", "Resultados de execução", ["state"], registry=registry)
stage_duration = Histogram("otm_stage_seconds", "Duração de etapas", ["stage"], registry=registry)
logger = logging.getLogger("otm_guard")


def event(name: str, **fields):
    logger.info(json.dumps({"event": name, **fields}, ensure_ascii=False, default=str))


@contextmanager
def stage(timings: dict, name: str):
    started = time.perf_counter()
    span: AbstractContextManager = nullcontext()
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry import trace

        span = trace.get_tracer("otm_guard").start_as_current_span(name)
    try:
        with span:
            yield
    finally:
        elapsed = time.perf_counter() - started
        timings[name] = round(elapsed, 6)
        stage_duration.labels(name).observe(elapsed)


def configure_tracing():
    """Sem endpoint configurado não existe exportação nem dependência de rede."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": "otm-guard"}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=5)))
        trace.set_tracer_provider(provider)
