"""ValidationAgent + connector tests (Phase 13: EXPLAIN wiring).

The fake connector is a plain object with an async explain — the agent only
needs duck-typing. SQL fixtures are inline literals at each call site.
"""

from app.agents.base import AgentConfig
from app.agents.validation.validation_agent import ValidationAgent


class FakeExplainConnector:
    def __init__(self, estimated_rows=0, plan_text="[plan]", error=None):
        self._rows = estimated_rows
        self._plan = plan_text
        self._error = error
        self.explain_calls = 0

    async def explain(self, sql):
        self.explain_calls += 1
        if self._error:
            raise self._error
        return {
            "plan_type": "EXPLAIN (FORMAT JSON)",
            "plan_text": self._plan,
            "estimated_cost": 100.0,
            "estimated_rows": self._rows,
        }


def _agent() -> ValidationAgent:
    return ValidationAgent(AgentConfig(model_name="deterministic"))


async def test_explain_estimate_flows_into_output():
    connector = FakeExplainConnector(estimated_rows=42, plan_text="[plan-json]")
    result = await _agent().execute(
        sql="SELECT region, revenue FROM public.sales GROUP BY region",
        connector=connector,
    )

    assert result.success is True
    assert result.output["row_estimate"] == 42
    assert result.output["explain_plan"] == "[plan-json]"
    assert result.output["requires_confirmation"] is False
    assert connector.explain_calls == 1


async def test_over_threshold_requires_confirmation():
    connector = FakeExplainConnector(estimated_rows=2_500_000)
    result = await _agent().execute(
        sql="SELECT region, revenue FROM public.sales GROUP BY region",
        connector=connector,
    )

    assert result.success is True, "large queries warn, they do not fail"
    assert result.output["requires_confirmation"] is True
    assert result.output["row_estimate"] == 2_500_000
    assert any("explicit user confirmation" in w for w in result.warnings)


async def test_explain_error_fails_open():
    connector = FakeExplainConnector(error=RuntimeError("explain blew up"))
    result = await _agent().execute(
        sql="SELECT region, revenue FROM public.sales GROUP BY region",
        connector=connector,
    )

    assert result.success is True
    assert result.output["requires_confirmation"] is False


async def test_no_connector_keeps_legacy_shape():
    result = await _agent().execute(
        sql="SELECT region, revenue FROM public.sales GROUP BY region",
    )

    assert result.success is True
    assert result.output["row_estimate"] is None
    assert result.output["requires_confirmation"] is False


async def test_rejected_sql_never_reaches_explain():
    connector = FakeExplainConnector(estimated_rows=5)
    result = await _agent().execute(
        # Multi-statement input: rejected by the injection check before any
        # EXPLAIN could run (destructive-pattern rejection is covered by the
        # committed validator tests).
        sql="SELECT region FROM public.sales; SELECT revenue FROM public.orders",
        connector=connector,
    )

    assert result.success is False
    assert connector.explain_calls == 0, "destructive SQL must not be EXPLAINed"
