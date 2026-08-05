"""GenBI application factory and server entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    setup_logging()

    # Observability: tracing, metrics, and auto-instrumentation. Each is guarded
    # so a missing collector/exporter never crashes boot — they degrade to logs.
    tracer_provider = None
    meter_provider = None
    try:
        from app.core.observability import init_metrics, init_tracing, instrument_app
        tracer_provider = init_tracing()
        meter_provider = init_metrics()
        instrument_app(app)
        logger.info("Observability wired: OTel tracing + metrics + instrumentation")
    except Exception as e:
        logger.warning(f"Observability init skipped (non-fatal): {e}")

    yield

    # Shutdown: flush traces and shut down providers cleanly.
    try:
        from app.core.observability import get_langfuse_tracer
        await get_langfuse_tracer().flush()
    except Exception as e:
        logger.debug(f"Langfuse flush failed (non-fatal): {e}")
    if tracer_provider is not None:
        try:
            tracer_provider.shutdown()
        except Exception:
            pass
    if meter_provider is not None:
        try:
            meter_provider.shutdown()
        except Exception:
            pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="GenBI",
        description="Generative BI Platform API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(api_router, prefix="/api/v1")

    # Prometheus /metrics endpoint. Served on the same port as the app so
    # infra/prometheus/prometheus.yml (which scrapes backend:8000) works without
    # a separate metrics port. OTel's PrometheusMetricReader is also active when
    # init_metrics() runs, but this route is the scrape target.
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
