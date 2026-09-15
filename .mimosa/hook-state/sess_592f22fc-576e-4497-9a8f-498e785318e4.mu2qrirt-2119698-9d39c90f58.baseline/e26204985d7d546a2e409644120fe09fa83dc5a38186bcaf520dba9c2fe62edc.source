"""Chat pipeline orchestration tests (Phase 13).

Exercises ChatService.process_query / process_query_stream end-to-end with:
- the REAL deterministic ValidationAgent (only its connector is faked)
- mocked LLM agents (router/nl2sql/chart_gen/narrative) via get_agent
- a mocked cache returning canned query results (skips the real connector
  in _step_execute)

Covers the happy path, early exits, and the >1M-row confirmation gate in
both sync and streaming modes.
"""

import json
from unittest.mock import AsyncMock, MagicMock

from app.agents.base import AgentResult
from app.agents.validation.validation_agent import ValidationAgent
from app.services.chat_service import ChatService

TENANT = "00000000-0000-0000-0000-000000000001"
ROWS = [{"region": "North", "total": 120000}, {"region": "South", "total": 95000}]
CHART_SPEC = {"chartType": "Bar Chart", "encodings": {}, "baseSize": {}, "data": {}}


def _llm_agent(output: dict, warnings: list[str] | None = None, success: bool = True):
    agent = MagicMock()
    agent.execute = AsyncMock(
        return_value=AgentResult(
            agent_name="mock", success=success, output=output, warnings=warnings or []
        )
    )
    return MagicMock(return_value=agent)  # agent_cls


def _patch_pipeline(
    monkeypatch,
    *,
    sql="SELECT region, SUM(revenue) FROM public.sales GROUP BY region",
    validation_sql=None,
    router_output=None,
    chart_output=None,
    narrative_text="Revenue is highest in the North.",
):
    agents = {
        "router": _llm_agent(router_output or {"intent": "chat_data", "dispatch_plan": []}),
        "nl2sql": _llm_agent({"sql": sql, "explanation": "groups revenue"}),
        # "validation" intentionally absent — the REAL ValidationAgent runs
        "chart_gen": _llm_agent(chart_output or {"chart_spec": CHART_SPEC}),
        "narrative": _llm_agent({"narrative": narrative_text}),
    }
    monkeypatch.setattr(
        "app.services.chat_service.get_agent",
        # LLM agents mocked; the REAL deterministic ValidationAgent runs
        lambda name: agents.get(name) or (ValidationAgent if name == "validation" else None),
    )

    # Cache: metric/fewshot/schema context hits (empty), query result hit
    cache = MagicMock()
    cache.get_metric_definitions = AsyncMock(return_value="")
    cache.get_schema_context = AsyncMock(return_value=[])
    cache.set_schema_context = AsyncMock()
    cache.get_few_shot_examples = AsyncMock(return_value=[])
    cache.set_few_shot_examples = AsyncMock()
    cache.get_query_result = AsyncMock(return_value=ROWS)
    cache.set_query_result = AsyncMock()
    monkeypatch.setattr("app.services.chat_service.get_cache", lambda: cache)

    # Conversations (Phase 14): mock persistence so no real DB connect is
    # attempted (keeps these tests fast and offline).
    import app.services.conversations as conversations_module

    monkeypatch.setattr(conversations_module, "create_conversation", AsyncMock(return_value=None))
    monkeypatch.setattr(
        conversations_module,
        "list_messages",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(conversations_module, "append_message", AsyncMock())

    # ValidationAgent's short-lived EXPLAIN connector
    explain_conn = MagicMock()
    explain_conn.explain = AsyncMock(
        return_value={
            "plan_type": "EXPLAIN (FORMAT JSON)",
            "plan_text": "[plan]",
            "estimated_cost": 10.0,
            "estimated_rows": 0,
        }
    )
    explain_conn.__aenter__ = AsyncMock(return_value=explain_conn)
    explain_conn.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "app.connectors.postgresql_connector.PostgreSQLConnector",
        MagicMock(return_value=explain_conn),
    )

    # Chart hallucination check: pass-through no-op
    validator = MagicMock()
    validator.warnings = []
    validator.fix_summary = []
    validator.corrected_spec = None
    validator.is_valid = True
    monkeypatch.setattr(
        "app.agents.validation.chart_validator.validate_chart_spec",
        lambda spec, data, auto_correct: validator,
    )

    return {"agents": agents, "cache": cache, "explain_conn": explain_conn}


async def _run_sync(service_args=None, **kwargs):
    service = ChatService(tenant_id=TENANT)
    return await service.process_query(
        query="show revenue by region",
        user_id="user-1",
        roles=["user"],
        **(service_args or {}),
        **kwargs,
    )


async def _collect_stream(**kwargs):
    service = ChatService(tenant_id=TENANT)
    events = []
    async for raw in service.process_query_stream(
        query="show revenue by region", user_id="user-1", roles=["user"], **kwargs
    ):
        events.append(json.loads(raw.removeprefix("data: ").strip()))
    return events


# ---------------------------------------------------------------------------
# Sync pipeline
# ---------------------------------------------------------------------------


async def test_sync_happy_path(monkeypatch):
    _patch_pipeline(monkeypatch)

    response = await _run_sync()

    assert response["sql"].startswith("SELECT")
    assert response["chart_spec"] == CHART_SPEC
    assert response["narrative"].startswith("Revenue is highest")
    assert response["requires_confirmation"] is False
    assert response["row_estimate"] == 0
    assert isinstance(response["warnings"], list)


async def test_sync_no_sql_early_exit(monkeypatch):
    _patch_pipeline(monkeypatch, sql=None)
    # nl2sql mock with success but empty sql → output lacks sql key
    response = await _run_sync()

    assert response["sql"] is None
    assert any("Could not generate SQL" in w for w in response["warnings"])


async def test_sync_validation_failed(monkeypatch):
    patch = _patch_pipeline(monkeypatch, sql="DELETE FROM public.sales")

    response = await _run_sync()

    assert response["sql"] is not None
    assert any("failed safety validation" in w for w in response["warnings"])
    # The destructive query was never EXPLAINed
    assert patch["explain_conn"].explain.await_count == 0


async def test_sync_confirmation_gate_blocks_then_proceeds(monkeypatch):
    patch = _patch_pipeline(monkeypatch)
    patch["explain_conn"].explain = AsyncMock(
        return_value={
            "plan_type": "EXPLAIN",
            "plan_text": "[big-plan]",
            "estimated_cost": 1e9,
            "estimated_rows": 2_000_000,
        }
    )

    # Without confirmation: stops before execution, flags set
    blocked = await _run_sync()
    assert blocked["requires_confirmation"] is True
    assert blocked["row_estimate"] == 2_000_000
    assert blocked["chart_spec"] is None, "no chart before confirmation"
    assert patch["cache"].get_query_result.await_count == 0, "execute never ran"

    # With confirmation: full pipeline
    confirmed = await _run_sync(confirm_large_query=True)
    assert confirmed["requires_confirmation"] is False
    assert confirmed["chart_spec"] == CHART_SPEC
    assert patch["cache"].get_query_result.await_count == 1


# ---------------------------------------------------------------------------
# Streaming pipeline
# ---------------------------------------------------------------------------


async def test_stream_event_order_happy_path(monkeypatch):
    _patch_pipeline(monkeypatch)

    events = await _collect_stream()

    order = [e["event"] for e in events]
    assert order == ["start", "intent", "sql", "validation", "data", "chart", "narrative", "done"]
    assert events[-1]["status"] == "complete"

    validation = events[3]
    assert validation["valid"] is True
    assert validation["requires_confirmation"] is False
    assert "row_estimate" in validation


async def test_stream_confirmation_required(monkeypatch):
    patch = _patch_pipeline(monkeypatch)
    patch["explain_conn"].explain = AsyncMock(
        return_value={
            "plan_type": "EXPLAIN",
            "plan_text": "[big]",
            "estimated_cost": 1e9,
            "estimated_rows": 5_000_000,
        }
    )

    events = await _collect_stream()

    assert [e["event"] for e in events] == ["start", "intent", "sql", "validation", "done"]
    done = events[-1]
    assert done["status"] == "confirmation_required"
    assert done["requires_confirmation"] is True
    assert done["row_estimate"] == 5_000_000
    assert patch["cache"].get_query_result.await_count == 0


async def test_stream_validation_failed_status(monkeypatch):
    _patch_pipeline(monkeypatch, sql="TRUNCATE TABLE public.sales")

    events = await _collect_stream()

    assert events[-1]["status"] == "validation_failed"
    assert events[3]["valid"] is False


async def test_stream_confirmed_resend_completes(monkeypatch):
    patch = _patch_pipeline(monkeypatch)
    patch["explain_conn"].explain = AsyncMock(
        return_value={
            "plan_type": "EXPLAIN",
            "plan_text": "[big]",
            "estimated_cost": 1e9,
            "estimated_rows": 5_000_000,
        }
    )

    events = await _collect_stream(confirm_large_query=True)

    assert events[-1]["status"] == "complete"
    assert patch["cache"].get_query_result.await_count == 1
