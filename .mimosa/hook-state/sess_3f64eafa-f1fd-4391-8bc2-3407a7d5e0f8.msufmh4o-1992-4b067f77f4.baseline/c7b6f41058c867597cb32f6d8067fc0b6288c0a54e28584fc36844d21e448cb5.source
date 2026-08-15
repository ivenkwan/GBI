"""Metrics endpoints — query the semantic layer via Cube.dev."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter()


class MetricSummary(BaseModel):
    name: str
    title: str
    description: str
    metric_type: str
    cube_name: str
    measure_name: str
    dimensions: list[str]
    time_dimensions: list[str]


class MetricListResponse(BaseModel):
    metrics: list[MetricSummary]
    count: int


class TimeDimensionSpec(BaseModel):
    dimension: str
    granularity: str = Field(pattern="^(day|week|month|quarter|year|hour)$")
    date_range: list[str] | None = Field(default=None, max_length=2)


class FilterSpec(BaseModel):
    member: str
    operator: str
    values: list[str] | None = None


class MetricQueryRequest(BaseModel):
    measures: list[str] = Field(min_length=1, max_length=5)
    dimensions: list[str] | None = Field(default=None, max_length=5)
    time_dimensions: list[TimeDimensionSpec] | None = Field(default=None, max_length=3)
    filters: list[FilterSpec] | None = None
    order: list[list[str]] | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0, le=100000)
    timezone: str = "UTC"


class MetricQueryResponse(BaseModel):
    data: list[dict]
    annotation: dict
    total: float | None
    query: dict
    latency_ms: float
    cached: bool


@router.get("/list", response_model=MetricListResponse)
async def list_metrics(
    user: dict = Depends(get_current_user),
):
    """List all available metrics from the semantic layer (Cube /meta)."""
    from app.semantic.cube_client import get_cube_client

    try:
        metrics = await get_cube_client().list_metrics()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CUBE_UNAVAILABLE",
                "message": f"Semantic layer unavailable: {type(e).__name__}",
            },
        ) from None

    # Skip the bare-measure-name aliases: one entry per measure, keyed by
    # the canonical `cube.measure` name.
    seen_names: set[str] = set()
    summaries: list[MetricSummary] = []
    for metric in metrics.values():
        if metric.name in seen_names:
            continue
        seen_names.add(metric.name)
        summaries.append(
            MetricSummary(
                name=metric.name,
                title=metric.title,
                description=metric.description,
                metric_type=metric.metric_type.value,
                cube_name=metric.cube_name,
                measure_name=metric.measure_name,
                dimensions=metric.dimensions,
                time_dimensions=metric.time_dimensions,
            )
        )

    return MetricListResponse(metrics=summaries, count=len(summaries))


@router.post("/query", response_model=MetricQueryResponse)
async def query_metrics(
    request: MetricQueryRequest,
    user: dict = Depends(get_current_user),
):
    """Execute a tenant-scoped metric query against Cube.dev.

    The tenant claim from the JWT is forwarded to Cube, which selects the
    per-tenant driver pool whose connections carry the RLS GUC — so results
    are tenant-isolated at the database layer (ADR 008).
    """
    from app.core.cache import get_cache
    from app.semantic.cube_client import get_cube_client

    tenant_id = user["tenant_id"]
    cube = get_cube_client()
    cache = get_cache()

    # Validate measures against the catalog before hitting Cube.
    try:
        catalog = await cube.list_metrics()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CUBE_UNAVAILABLE",
                "message": f"Semantic layer unavailable: {type(e).__name__}",
            },
        ) from None

    unknown = [m for m in request.measures if m not in catalog]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_METRIC",
                "message": f"Unknown measure(s): {', '.join(unknown)}",
            },
        )

    # Canonical query form — used as the cache key, so every result-affecting
    # parameter must be included.
    cube_query: dict = {
        "measures": request.measures,
        "limit": request.limit,
        "offset": request.offset,
        "timezone": request.timezone,
    }
    if request.dimensions:
        cube_query["dimensions"] = request.dimensions
    if request.time_dimensions:
        cube_query["timeDimensions"] = [
            {
                "dimension": td.dimension,
                "granularity": td.granularity,
                **({"dateRange": td.date_range} if td.date_range else {}),
            }
            for td in request.time_dimensions
        ]
    if request.filters:
        cube_query["filters"] = [
            {
                "member": f.member,
                "operator": f.operator,
                **({"values": f.values} if f.values is not None else {}),
            }
            for f in request.filters
        ]
    if request.order:
        cube_query["order"] = {field: direction for field, direction in request.order}

    cached_result = await cache.get_cube_query_result(cube_query, tenant_id)
    if cached_result is not None:
        return MetricQueryResponse(cached=True, **cached_result)

    try:
        result = await cube.query(
            metrics=request.measures,
            dimensions=request.dimensions,
            time_dimensions=cube_query.get("timeDimensions"),
            filters=cube_query.get("filters"),
            order=request.order,
            limit=request.limit,
            offset=request.offset,
            timezone=request.timezone,
            tenant_id=tenant_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CUBE_UNAVAILABLE",
                "message": f"Semantic layer query failed: {type(e).__name__}",
            },
        ) from None

    payload = {
        "data": result.data,
        "annotation": result.annotation,
        "total": result.total,
        "query": result.query,
        "latency_ms": round(result.query_latency_ms, 2),
    }
    await cache.set_cube_query_result(cube_query, tenant_id, payload)

    return MetricQueryResponse(cached=result.cached, **payload)
