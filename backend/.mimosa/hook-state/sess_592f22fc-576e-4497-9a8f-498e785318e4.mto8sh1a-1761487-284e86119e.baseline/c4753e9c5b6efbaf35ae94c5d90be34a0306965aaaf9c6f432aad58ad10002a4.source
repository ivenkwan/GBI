"""Tests for the Phase 11 ChatService wiring: schema context and few-shot
examples flow into the NL2SQL agent, with graceful degradation on failure.

All collaborators are mocked (cache, Cube client, retrieval, agent) — these
tests pin the SERVICE wiring, not the retrieval internals (covered in
tests/services/test_schema_retrieval.py).
"""

from unittest.mock import AsyncMock, MagicMock

from app.agents.base import AgentResult
from app.services.chat_service import ChatService

TENANT = "00000000-0000-0000-0000-000000000001"


def _make_agent():
    agent = MagicMock()
    agent.execute = AsyncMock(
        return_value=AgentResult(agent_name="nl2sql", success=True, output={"sql": "SELECT 1"})
    )
    return agent


def _make_cache():
    cache = MagicMock()
    cache.get_metric_definitions = AsyncMock(return_value="metric context")
    cache.get_schema_context = AsyncMock(return_value=None)
    cache.set_schema_context = AsyncMock()
    cache.get_few_shot_examples = AsyncMock(return_value=None)
    cache.set_few_shot_examples = AsyncMock()
    return cache


def _patch_all(monkeypatch, agent, cache, schema_ctx=None, few_shot=None):
    agent_cls = MagicMock(return_value=agent)
    monkeypatch.setattr("app.services.chat_service.get_agent", lambda name: agent_cls)
    monkeypatch.setattr("app.services.chat_service.get_cache", lambda: cache)

    monkeypatch.setattr(
        "app.services.schema_retrieval.retrieve_schema_context",
        AsyncMock(return_value=schema_ctx or []),
    )
    monkeypatch.setattr(
        "app.services.schema_retrieval.retrieve_few_shot_examples",
        AsyncMock(return_value=few_shot or []),
    )


async def test_schema_and_few_shot_flow_into_agent(monkeypatch):
    agent = _make_agent()
    cache = _make_cache()
    schema_ctx = [{"table_name": "public.sales", "description": "", "columns": []}]
    few_shot = [{"nl_query": "q", "expected_sql": "s"}]
    _patch_all(monkeypatch, agent, cache, schema_ctx=schema_ctx, few_shot=few_shot)

    service = ChatService(tenant_id=TENANT)
    sql, warnings = await service._step_nl2sql("revenue by region", "user-1")

    assert sql == "SELECT 1"
    assert warnings == []

    kwargs = agent.execute.call_args.kwargs
    assert kwargs["schema_context"] == schema_ctx
    assert kwargs["few_shot_examples"] == few_shot
    assert kwargs["metric_definitions"] == "metric context"

    # Retrieval results were cached under the tenant
    cache.set_schema_context.assert_awaited_once()
    cache.set_few_shot_examples.assert_awaited_once()


async def test_cached_context_skips_retrieval(monkeypatch):
    agent = _make_agent()
    cache = _make_cache()
    cached_schema = [{"table_name": "public.orders", "description": "", "columns": []}]
    cached_few_shot = [{"nl_query": "cq", "expected_sql": "cs"}]
    cache.get_schema_context = AsyncMock(return_value=cached_schema)
    cache.get_few_shot_examples = AsyncMock(return_value=cached_few_shot)

    retrieve_schema = AsyncMock(return_value=[])
    retrieve_few_shot = AsyncMock(return_value=[])
    _patch_all(monkeypatch, agent, cache)
    import app.services.schema_retrieval as sr

    monkeypatch.setattr(sr, "retrieve_schema_context", retrieve_schema)
    monkeypatch.setattr(sr, "retrieve_few_shot_examples", retrieve_few_shot)

    service = ChatService(tenant_id=TENANT)
    await service._step_nl2sql("orders", "user-1")

    retrieve_schema.assert_not_awaited()
    retrieve_few_shot.assert_not_awaited()
    assert agent.execute.call_args.kwargs["schema_context"] == cached_schema
    assert agent.execute.call_args.kwargs["few_shot_examples"] == cached_few_shot


async def test_retrieval_failure_degrades_gracefully(monkeypatch):
    agent = _make_agent()
    cache = _make_cache()
    _patch_all(monkeypatch, agent, cache)

    import app.services.schema_retrieval as sr

    monkeypatch.setattr(
        sr, "retrieve_schema_context", AsyncMock(side_effect=RuntimeError("db down"))
    )
    monkeypatch.setattr(
        sr, "retrieve_few_shot_examples", AsyncMock(side_effect=RuntimeError("db down"))
    )

    service = ChatService(tenant_id=TENANT)
    sql, warnings = await service._step_nl2sql("revenue", "user-1")

    # Pipeline continues: SQL generated, context empty, no warnings leaked
    assert sql == "SELECT 1"
    assert warnings == []
    kwargs = agent.execute.call_args.kwargs
    assert kwargs["schema_context"] == []
    assert kwargs["few_shot_examples"] == []
