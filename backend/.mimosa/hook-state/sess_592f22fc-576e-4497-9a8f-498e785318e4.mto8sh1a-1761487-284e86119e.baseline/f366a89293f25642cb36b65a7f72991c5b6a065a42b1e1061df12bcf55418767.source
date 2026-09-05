"""Tests for the Cube.dev semantic layer client."""

import os

import pytest

from app.semantic.cube_client import (
    CubeClient,
    MetricDefinition,
    MetricType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cube_client():
    """CubeClient with a fake API URL — all tests mock the HTTP layer.

    The secret is env-overridable but defaults to a clearly fake value; no
    real credential is ever exercised here.
    """
    return CubeClient(
        api_url="http://fake-cube:4000/cubejs-api/v1",
        api_secret=os.environ.get("CUBEJS_TEST_API_SECRET", "test-secret"),
        cache_ttl_seconds=60,
    )


@pytest.fixture
def mock_meta_response():
    """Realistic Cube /meta API response."""
    return {
        "cubes": [
            {
                "name": "revenue",
                "title": "Revenue",
                "measures": [
                    {
                        "name": "revenue_amount",
                        "title": "Revenue Amount",
                        "shortTitle": "Revenue",
                        "type": "sum",
                        "description": "Total recognized revenue in USD",
                        "format": {"currency": "USD"},
                    },
                    {
                        "name": "revenue_count",
                        "title": "Transaction Count",
                        "type": "count",
                        "description": "Number of revenue transactions",
                    },
                ],
                "dimensions": [
                    {"name": "region", "title": "Region", "type": "string"},
                    {"name": "product_category", "title": "Product Category", "type": "string"},
                    {"name": "transaction_date", "title": "Transaction Date", "type": "time"},
                ],
            },
            {
                "name": "users",
                "title": "Users",
                "measures": [
                    {
                        "name": "active_users",
                        "title": "Active Users",
                        "type": "countDistinct",
                        "description": "Distinct users with activity in the period",
                    },
                ],
                "dimensions": [
                    {"name": "signup_date", "title": "Signup Date", "type": "time"},
                    {"name": "country", "title": "Country", "type": "string"},
                ],
            },
        ]
    }


@pytest.fixture
def mock_load_response():
    """Realistic Cube /load API response."""
    return {
        "query": {"measures": ["revenue.revenue_amount"], "dimensions": ["revenue.region"]},
        "data": [
            {"revenue.revenue_amount": 120000, "revenue.region": "North"},
            {"revenue.revenue_amount": 95000, "revenue.region": "South"},
        ],
        "annotation": {
            "measures": {
                "revenue.revenue_amount": {
                    "title": "Revenue Amount",
                    "shortTitle": "Revenue",
                    "type": "sum",
                    "format": {"currency": "USD"},
                },
            },
            "dimensions": {
                "revenue.region": {"title": "Region", "type": "string"},
            },
        },
    }


# ---------------------------------------------------------------------------
# _parse_meta tests
# ---------------------------------------------------------------------------


class TestParseMeta:
    """Tests for _parse_meta — no network calls, pure parsing."""

    def test_parses_measures_as_metrics(self, cube_client, mock_meta_response):
        """Each measure should become a MetricDefinition indexed by cube.measure."""
        result = cube_client._parse_meta(mock_meta_response)

        assert "revenue.revenue_amount" in result.metrics
        metric = result.metrics["revenue.revenue_amount"]
        assert metric.name == "revenue.revenue_amount"
        assert metric.title == "Revenue Amount"
        assert metric.description == "Total recognized revenue in USD"
        assert metric.metric_type == MetricType.SUM
        assert metric.cube_name == "revenue"
        assert metric.measure_name == "revenue_amount"
        assert metric.format == {"currency": "USD"}

    def test_parses_count_distinct_metric(self, cube_client, mock_meta_response):
        """countDistinct measures should map to MetricType.COUNT_DISTINCT."""
        result = cube_client._parse_meta(mock_meta_response)

        metric = result.metrics["users.active_users"]
        assert metric.metric_type == MetricType.COUNT_DISTINCT
        assert metric.cube_name == "users"
        assert metric.measure_name == "active_users"

    def test_extracts_dimensions(self, cube_client, mock_meta_response):
        """Non-time dimensions should be attached to the metric."""
        result = cube_client._parse_meta(mock_meta_response)

        metric = result.metrics["revenue.revenue_amount"]
        assert "region" in metric.dimensions
        assert "product_category" in metric.dimensions
        assert "transaction_date" not in metric.dimensions  # time dimension excluded

    def test_extracts_time_dimensions(self, cube_client, mock_meta_response):
        """Time dimensions should be separated from regular dimensions."""
        result = cube_client._parse_meta(mock_meta_response)

        metric = result.metrics["revenue.revenue_amount"]
        assert "transaction_date" in metric.time_dimensions

    def test_short_name_lookup(self, cube_client, mock_meta_response):
        """Metrics should also be accessible by just the measure name."""
        result = cube_client._parse_meta(mock_meta_response)

        assert "revenue_amount" in result.metrics
        assert result.metrics["revenue_amount"].cube_name == "revenue"

    def test_empty_meta(self, cube_client):
        """Empty meta response should produce empty metrics."""
        result = cube_client._parse_meta({"cubes": []})
        assert result.metrics == {}
        assert result.cubes == []

    def test_handles_missing_fields(self, cube_client):
        """Measures without optional fields should still parse."""
        raw = {
            "cubes": [
                {
                    "name": "test",
                    "measures": [{"name": "count"}],
                    "dimensions": [],
                }
            ]
        }
        result = cube_client._parse_meta(raw)

        metric = result.metrics["test.count"]
        assert metric.title == "count"  # falls back to name
        assert metric.description == ""
        assert metric.metric_type == MetricType.SUM  # default for unknown types
        assert metric.dimensions == []
        assert metric.time_dimensions == []

    def test_multiple_cubes(self, cube_client, mock_meta_response):
        """Metrics from all cubes should be in the result."""
        result = cube_client._parse_meta(mock_meta_response)

        cube_names = {m.cube_name for m in result.metrics.values()}
        assert "revenue" in cube_names
        assert "users" in cube_names

    def test_infer_metric_type_running_total(self, cube_client):
        """runningTotal type should map correctly."""
        assert cube_client._infer_metric_type("runningTotal") == MetricType.RUNNING_TOTAL

    def test_infer_metric_type_unknown(self, cube_client):
        """Unknown types should default to SUM."""
        assert cube_client._infer_metric_type("unknown_type") == MetricType.SUM


# ---------------------------------------------------------------------------
# format_metrics_for_llm tests
# ---------------------------------------------------------------------------


class TestFormatMetricsForLLM:
    """Tests for LLM context formatting."""

    def test_formats_single_metric(self, cube_client):
        """Format a single metric definition."""
        metrics = {
            "revenue.total": MetricDefinition(
                name="revenue.total",
                title="Total Revenue",
                description="Sum of all recognized revenue",
                metric_type=MetricType.SUM,
                cube_name="revenue",
                measure_name="total",
                dimensions=["region", "product"],
                time_dimensions=["transaction_date"],
                format={"currency": "USD"},
            ),
        }

        result = cube_client.format_metrics_for_llm(metrics)

        assert "**revenue.total**" in result
        assert "Sum of all recognized revenue" in result
        assert "revenue" in result  # cube name
        assert "region" in result
        assert "transaction_date" in result

    def test_formats_multiple_metrics(self, cube_client):
        """Format multiple metrics."""
        metrics = {
            "a.total": MetricDefinition(
                name="a.total",
                title="A",
                description="Metric A",
                metric_type=MetricType.SUM,
                cube_name="a",
                measure_name="total",
            ),
            "b.count": MetricDefinition(
                name="b.count",
                title="B",
                description="Metric B",
                metric_type=MetricType.COUNT,
                cube_name="b",
                measure_name="count",
            ),
        }

        result = cube_client.format_metrics_for_llm(metrics)

        assert "**a.total**" in result
        assert "**b.count**" in result

    def test_empty_metrics(self, cube_client):
        """Empty metrics should produce a clear message."""
        result = cube_client.format_metrics_for_llm({})
        assert "No metrics available" in result

    def test_filters_by_metric_names(self, cube_client):
        """Should only include requested metric names."""
        metrics = {
            "a.total": MetricDefinition(
                name="a.total",
                title="A",
                description="A",
                metric_type=MetricType.SUM,
                cube_name="a",
                measure_name="total",
            ),
            "b.count": MetricDefinition(
                name="b.count",
                title="B",
                description="B",
                metric_type=MetricType.COUNT,
                cube_name="b",
                measure_name="count",
            ),
        }

        result = cube_client.format_metrics_for_llm(metrics=metrics, metric_names=["a.total"])

        assert "**a.total**" in result
        assert "**b.count**" not in result

    def test_format_metric_for_prompt(self, cube_client):
        """Single metric prompt line."""
        metric = MetricDefinition(
            name="revenue.total",
            title="Total Revenue",
            description="Sum of all recognized revenue",
            metric_type=MetricType.SUM,
            cube_name="revenue",
            measure_name="total",
            dimensions=["region"],
            format={"currency": "USD"},
        )

        result = cube_client.format_metric_for_prompt("revenue.total", metric)

        assert "**revenue.total**" in result
        assert "currency (USD)" in result

    def test_percent_format(self, cube_client):
        """Percent format should be noted."""
        metric = MetricDefinition(
            name="conversion.rate",
            title="Conversion Rate",
            description="Conversion rate",
            metric_type=MetricType.RATIO,
            cube_name="conversion",
            measure_name="rate",
            format={"percent": True},
        )

        result = cube_client.format_metric_for_prompt("conversion.rate", metric)
        assert "percent" in result


# ---------------------------------------------------------------------------
# MetricDefinition smoke tests
# ---------------------------------------------------------------------------


class TestMetricDefinition:
    """Verify MetricDefinition dataclass behavior."""

    def test_defaults(self):
        """Fields with defaults should be empty."""
        m = MetricDefinition(
            name="test",
            title="Test",
            description="",
            metric_type=MetricType.SUM,
            cube_name="c",
            measure_name="m",
        )
        assert m.dimensions == []
        assert m.time_dimensions == []
        assert m.format is None

    def test_equality(self):
        """Two definitions with same fields should be equal."""
        a = MetricDefinition(
            name="x",
            title="X",
            description="",
            metric_type=MetricType.SUM,
            cube_name="c",
            measure_name="m",
        )
        b = MetricDefinition(
            name="x",
            title="X",
            description="",
            metric_type=MetricType.SUM,
            cube_name="c",
            measure_name="m",
        )
        assert a == b


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------


class TestGetCubeClient:
    """Tests for the singleton get_cube_client()."""

    def test_returns_same_instance(self):
        """Multiple calls should return the same instance."""
        # Force reset for test isolation
        import app.semantic.cube_client as mod
        from app.semantic.cube_client import get_cube_client

        mod._cube_client = None

        client1 = get_cube_client()
        client2 = get_cube_client()
        assert client1 is client2

    def test_uses_settings_defaults(self):
        """Without args, should use settings.CUBE_API_URL."""
        import app.semantic.cube_client as mod
        from app.semantic.cube_client import get_cube_client

        mod._cube_client = None

        client = get_cube_client()
        assert client.api_url.endswith("/cubejs-api/v1")
