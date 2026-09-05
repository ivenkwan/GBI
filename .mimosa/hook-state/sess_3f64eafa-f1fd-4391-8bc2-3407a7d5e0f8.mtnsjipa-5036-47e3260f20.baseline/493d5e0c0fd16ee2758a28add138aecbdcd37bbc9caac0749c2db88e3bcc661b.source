"""OpenTelemetry observability setup — tracing, metrics, and logging integration.

Wires up:
- OpenTelemetry SDK with automatic instrumentation for FastAPI, SQLAlchemy, httpx
- Langfuse exporter for LLM trace collection
- Prometheus metrics endpoint at /metrics
- Structured logging correlation via trace_id injection

Architecture:
    FastAPI Request → OTel Span → Agent Span → LLM Call Span → DB Query Span
                                  ↓
                            Langfuse Trace
                                   ↓
                            Audit Log Record
"""

import os
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, DEPLOYMENT_ENVIRONMENT
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import settings
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Resource (identifies this service in traces)
# ---------------------------------------------------------------------------

def _build_resource() -> Resource:
    """Build the OTel resource with service metadata."""
    return Resource.create({
        SERVICE_NAME: "genbi-backend",
        DEPLOYMENT_ENVIRONMENT: settings.APP_ENV,
        "service.version": "0.1.0",
        "service.namespace": "genbi",
    })


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------


def init_tracing() -> TracerProvider | None:
    """Initialize OpenTelemetry tracing.

    Exports spans to OTLP collector (if configured) and console in dev.

    Returns:
        TracerProvider or None if tracing is disabled.
    """
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not otlp_endpoint and settings.APP_ENV == "production":
        logger.warning("OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled")
        return None

    resource = _build_resource()
    provider = TracerProvider(resource=resource)

    # OTLP exporter (gRPC)
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter, max_queue_size=2048, max_export_batch_size=512)
        )
        logger.info(f"OTel tracing enabled — exporting to {otlp_endpoint}")

    # Console exporter for development
    if settings.DEBUG:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )

    trace.set_tracer_provider(provider)
    return provider


def instrument_app(app):
    """Auto-instrument FastAPI, SQLAlchemy, and httpx.

    Call this after app creation but before any requests.
    """
    # FastAPI auto-instrumentation
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/health,/metrics,/favicon.ico",
        tracer_provider=trace.get_tracer_provider(),
    )

    # HTTPX client instrumentation (for outbound HTTP calls — Cube.dev, LLM APIs)
    HTTPXClientInstrumentor().instrument()

    # SQLAlchemy instrumentation
    SQLAlchemyInstrumentor().instrument(
        enable_commenter=True,
        commenter_options={"enable_db_statement_parameters": False},
    )

    logger.info("OpenTelemetry instrumentation applied to FastAPI, httpx, SQLAlchemy")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def init_metrics() -> MeterProvider | None:
    """Initialize OpenTelemetry metrics with Prometheus endpoint.

    Returns:
        MeterProvider or None if metrics are disabled.
    """
    resource = _build_resource()
    readers = []

    # Prometheus endpoint (always available at /metrics)
    prometheus_reader = PrometheusMetricReader()
    readers.append(prometheus_reader)

    # OTLP metrics exporter (if configured)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        otlp_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=otlp_endpoint),
            export_interval_millis=30_000,
        )
        readers.append(otlp_reader)

    provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(provider)

    # Create application-level meters
    meter = metrics.get_meter("genbi")

    # Chat pipeline metrics
    chat_requests_counter = meter.create_counter(
        "genbi.chat.requests",
        description="Total chat requests processed",
        unit="requests",
    )
    chat_latency_histogram = meter.create_histogram(
        "genbi.chat.latency",
        description="End-to-end chat pipeline latency",
        unit="ms",
    )

    # SQL generation metrics
    sql_generation_counter = meter.create_counter(
        "genbi.sql.generated",
        description="Total SQL queries generated",
        unit="queries",
    )
    sql_validation_failures = meter.create_counter(
        "genbi.sql.validation_failures",
        description="SQL queries rejected by ValidationAgent",
        unit="queries",
    )

    # LLM call metrics
    llm_token_counter = meter.create_counter(
        "genbi.llm.tokens",
        description="Total LLM tokens consumed",
        unit="tokens",
    )
    llm_call_latency = meter.create_histogram(
        "genbi.llm.latency",
        description="LLM API call latency",
        unit="ms",
    )

    # Cache metrics
    cache_hits = meter.create_counter(
        "genbi.cache.hits",
        description="Cache hit count",
        unit="hits",
    )
    cache_misses = meter.create_counter(
        "genbi.cache.misses",
        description="Cache miss count",
        unit="misses",
    )

    logger.info("OTel metrics initialized — Prometheus endpoint at /metrics")
    return provider


# ---------------------------------------------------------------------------
# Langfuse integration
# ---------------------------------------------------------------------------


class LangfuseTracer:
    """Langfuse LLM tracing integration.

    Every LLM call is traced through Langfuse for:
    - Input/output token tracking
    - Latency measurement
    - Model version tracking
    - Cost allocation per tenant/user

    Langfuse traces are tagged with:
        project=genbi, env={APP_ENV}, tenant_id, user_id, session_id
    """

    def __init__(self):
        self._client = None
        self._enabled = False

    async def _init(self) -> None:
        """Lazy-init Langfuse client."""
        if self._client is not None:
            return

        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                secret_key=settings.LANGFUSE_SECRET_KEY,
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                host=settings.LANGFUSE_HOST,
                release="0.1.0",
            )
            self._enabled = True
            logger.info("Langfuse tracing enabled")
        except ImportError:
            logger.warning("langfuse package not installed — LLM tracing disabled")
            self._enabled = False
        except Exception as e:
            logger.warning(f"Langfuse init failed — LLM tracing disabled: {e}")
            self._enabled = False

    async def trace_llm_call(
        self,
        name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        user_id: str = "",
        tenant_id: str = "",
        session_id: str = "",
        input_prompt: str = "",
        output_content: str = "",
        metadata: dict | None = None,
    ) -> str | None:
        """Record an LLM call trace in Langfuse.

        Returns:
            Trace ID or None if tracing is disabled.
        """
        if not self._enabled:
            await self._init()
            if not self._enabled:
                return None

        try:
            trace = self._client.trace(
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata={
                    "model": model,
                    "tenant_id": tenant_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                    "env": settings.APP_ENV,
                    **(metadata or {}),
                },
            )

            # Record the generation span
            trace.generation(
                name=f"{name}-generation",
                model=model,
                input=input_prompt[:2000] if input_prompt else None,
                output=output_content[:2000] if output_content else None,
                usage={
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens,
                },
                metadata={
                    "latency_ms": latency_ms,
                    "tenant_id": tenant_id,
                },
            )

            return trace.id

        except Exception as e:
            logger.debug(f"Langfuse trace failed (non-fatal): {e}")
            return None

    async def flush(self) -> None:
        """Flush pending traces before shutdown."""
        if self._client and self._enabled:
            try:
                self._client.flush()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Trace context helpers
# ---------------------------------------------------------------------------


def get_current_trace_id() -> str | None:
    """Get the current OpenTelemetry trace ID for log correlation."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, "032x")
    return None


def create_span(name: str, attributes: dict | None = None):
    """Create a manual span for agent operations.

    Usage:
        tracer = trace.get_tracer("genbi")
        with tracer.start_as_current_span("nl2sql.generate") as span:
            span.set_attribute("query.length", len(query))
            result = await agent.execute(query=query)
            span.set_attribute("sql.length", len(result.output.get("sql", "")))
    """
    tracer = trace.get_tracer("genbi")
    return tracer.start_as_current_span(name, attributes=attributes or {})


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_langfuse_tracer: LangfuseTracer | None = None


def get_langfuse_tracer() -> LangfuseTracer:
    """Get or create the Langfuse tracer singleton."""
    global _langfuse_tracer
    if _langfuse_tracer is None:
        _langfuse_tracer = LangfuseTracer()
    return _langfuse_tracer
