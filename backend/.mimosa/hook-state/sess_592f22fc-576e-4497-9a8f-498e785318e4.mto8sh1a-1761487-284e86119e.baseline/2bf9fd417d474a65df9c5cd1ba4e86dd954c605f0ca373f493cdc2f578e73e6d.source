"""Tests for Phase 9 CubeClient fixes: JWT auth, raw-meta caching,
agent-context metric ranking. All offline — no Cube, Redis, or DB.
"""

from datetime import UTC, datetime

from app.semantic.cube_client import (
    MAX_AGENT_CONTEXT_METRICS,
    CubeClient,
    MetricDefinition,
    MetricType,
)

# ---------------------------------------------------------------------------
# JWT auth
# ---------------------------------------------------------------------------


def test_auth_token_none_without_secret():
    client = CubeClient(api_url="http://cube", api_secret="")
    assert client._auth_token() is None


def test_auth_token_is_decodable_jwt():
    from jose import jwt

    secret = "test-secret"
    client = CubeClient(api_url="http://cube", api_secret=secret)

    token = client._auth_token()
    assert token is not None

    payload = jwt.decode(token, secret, algorithms=["HS256"])
    assert "exp" in payload
    assert payload["exp"] > datetime.now(UTC).timestamp()


def test_auth_token_cached_until_near_expiry():
    secret = "test-secret"
    client = CubeClient(api_url="http://cube", api_secret=secret)

    first = client._auth_token()
    second = client._auth_token()
    assert first == second, "token should be cached, not re-minted per request"


# ---------------------------------------------------------------------------
# Raw-meta cache re-parse (Redis hit path)
# ---------------------------------------------------------------------------


RAW_META = {
    "cubes": [
        {
            "name": "Sales",
            "title": "Sales",
            "measures": [{"name": "revenue_total", "title": "Total Revenue", "type": "sum"}],
            "dimensions": [
                {"name": "region", "type": "string"},
                {"name": "transaction_date", "type": "time"},
            ],
        }
    ]
}


async def test_meta_cache_hit_reparses_metrics(monkeypatch):
    """A raw /meta payload from cache must come back WITH parsed metrics."""
    client = CubeClient(api_url="http://cube", api_secret="s")

    async def fake_get_cached(key):
        return RAW_META

    async def fake_set_cached(key, value):
        pass

    monkeypatch.setattr(client, "_get_cached", fake_get_cached)
    monkeypatch.setattr(client, "_set_cached", fake_set_cached)

    meta = await client.get_meta()
    assert "Sales.revenue_total" in meta.metrics
    assert meta.metrics["Sales.revenue_total"].cube_name == "Sales"


# ---------------------------------------------------------------------------
# Agent-context metric ranking
# ---------------------------------------------------------------------------


def _metric(
    name: str, title: str = "", description: str = "", cube: str = "Sales"
) -> MetricDefinition:
    return MetricDefinition(
        name=name,
        title=title or name,
        description=description,
        metric_type=MetricType.SUM,
        cube_name=cube,
        measure_name=name,
    )


def _metric_dict(*metrics: MetricDefinition) -> dict[str, MetricDefinition]:
    """Key by metric.name — mirrors how _parse_meta indexes metrics."""
    return {m.name: m for m in metrics}


def test_rank_metrics_scores_name_over_description():
    metrics = _metric_dict(
        _metric("Sales.revenue_total", description="revenue things"),
        _metric("Sales.units_sold", description="revenue mentioned in passing"),
    )
    ranked = CubeClient._rank_metrics_for_query(metrics, "total revenue")
    assert ranked[0].name == "Sales.revenue_total"


def test_rank_metrics_empty_when_no_overlap():
    metrics = _metric_dict(_metric("Sales.revenue_total"))
    assert CubeClient._rank_metrics_for_query(metrics, "completely unrelated") == []


def test_rank_metrics_respects_limit():
    metrics = _metric_dict(*(_metric(f"Sales.revenue_{i}") for i in range(50)))
    ranked = CubeClient._rank_metrics_for_query(metrics, "revenue", limit=20)
    assert len(ranked) == 20


async def test_agent_context_ranks_when_over_limit(monkeypatch):
    client = CubeClient(api_url="http://cube", api_secret="s")

    metrics = _metric_dict(
        _metric("Sales.revenue_total"),
        *(
            _metric(f"Noise.metric_{i}", description="unrelated")
            for i in range(MAX_AGENT_CONTEXT_METRICS + 4)
        ),
    )

    async def fake_list_metrics(force_refresh=False):
        return metrics

    monkeypatch.setattr(client, "list_metrics", fake_list_metrics)

    context = await client.get_agent_context(query="show me total revenue")
    assert "Sales.revenue_total" in context
    assert "Noise.metric_1" not in context
    assert len(metrics) > MAX_AGENT_CONTEXT_METRICS  # precondition


async def test_agent_context_full_list_when_no_match(monkeypatch):
    client = CubeClient(api_url="http://cube", api_secret="s")

    metrics = _metric_dict(
        *(_metric(f"Sales.metric_{i}") for i in range(MAX_AGENT_CONTEXT_METRICS + 3))
    )

    async def fake_list_metrics(force_refresh=False):
        return metrics

    monkeypatch.setattr(client, "list_metrics", fake_list_metrics)

    context = await client.get_agent_context(query="something entirely different")
    assert f"Sales.metric_{MAX_AGENT_CONTEXT_METRICS + 2}" in context
