"""Phase 14 wiring tests: NL2SQL prompt history section + ChatService turns.

The ChatService tests patch the conversations service module (the same
seam the endpoint uses) and reuse the pipeline-test harness shape from
test_chat_pipeline.py for the rest.
"""

import json
from unittest.mock import AsyncMock, MagicMock

from app.agents.base import AgentConfig
from app.agents.nl2sql.nl2sql_agent import NL2SQLAgent
from app.services.chat_service import ChatService

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"
CONV = "00000000-0000-0000-0000-0000000000bb"


# ---------------------------------------------------------------------------
# NL2SQLAgent prompt section
# ---------------------------------------------------------------------------


def test_history_section_rendered():
    agent = NL2SQLAgent(AgentConfig(model_name="test"))
    message = agent._build_user_message(
        query="now break that down by region",
        schema_context=None,
        few_shot_examples=None,
        metric_definitions=None,
        tenant_id=TENANT,
        history=[
            {"role": "user", "content": "total revenue", "generated_sql": None},
            {
                "role": "assistant",
                "content": "Total revenue is $1.2M",
                "generated_sql": "SELECT SUM(revenue) FROM public.sales",
            },
        ],
    )

    assert "## Conversation History" in message
    assert "User: total revenue" in message
    assert "Assistant: Total revenue is $1.2M" in message
    assert "[SQL: SELECT SUM(revenue) FROM public.sales]" in message
    # The current question stays prominent
    assert "## User Question" in message


def test_no_history_section_when_empty():
    agent = NL2SQLAgent(AgentConfig(model_name="test"))
    message = agent._build_user_message(
        query="total revenue",
        schema_context=None,
        few_shot_examples=None,
        metric_definitions=None,
        tenant_id=TENANT,
        history=[],
    )
    assert "## Conversation History" not in message


# ---------------------------------------------------------------------------
# ChatService conversation wiring
# ---------------------------------------------------------------------------


def _patch_conversations(monkeypatch, history=None, create_returns=CONV):
    import app.services.conversations as svc

    monkeypatch.setattr(svc, "create_conversation", AsyncMock(return_value=create_returns))
    monkeypatch.setattr(svc, "list_messages", AsyncMock(return_value=history or []))
    monkeypatch.setattr(svc, "append_message", AsyncMock())
    return svc


def _patch_agents(monkeypatch):
    """Only the LLM agents; the real ValidationAgent runs (connector faked)."""
    from app.agents.base import AgentResult
    from app.agents.validation.validation_agent import ValidationAgent

    def llm_cls(output):
        agent = MagicMock()
        agent.execute = AsyncMock(
            return_value=AgentResult(agent_name="mock", success=True, output=output)
        )
        return MagicMock(return_value=agent)

    agents = {
        "router": llm_cls({"intent": "chat_data", "dispatch_plan": []}),
        "nl2sql": llm_cls({"sql": "SELECT region FROM public.sales"}),
        "chart_gen": llm_cls({"chart_spec": {}}),
        "narrative": llm_cls({"narrative": "North leads."}),
    }

    monkeypatch.setattr(
        "app.services.chat_service.get_agent",
        lambda name: agents.get(name) or (ValidationAgent if name == "validation" else None),
    )

    cache = MagicMock()
    cache.get_metric_definitions = AsyncMock(return_value="")
    cache.get_schema_context = AsyncMock(return_value=[])
    cache.set_schema_context = AsyncMock()
    cache.get_few_shot_examples = AsyncMock(return_value=[])
    cache.set_few_shot_examples = AsyncMock()
    cache.get_query_result = AsyncMock(return_value=[{"region": "North"}])
    cache.set_query_result = AsyncMock()
    monkeypatch.setattr("app.services.chat_service.get_cache", lambda: cache)

    explain_conn = MagicMock()
    explain_conn.explain = AsyncMock(
        return_value={
            "plan_type": "EXPLAIN",
            "plan_text": "[p]",
            "estimated_cost": 1.0,
            "estimated_rows": 0,
        }
    )
    explain_conn.__aenter__ = AsyncMock(return_value=explain_conn)
    explain_conn.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "app.connectors.postgresql_connector.PostgreSQLConnector",
        MagicMock(return_value=explain_conn),
    )

    # Chart validator no-op
    validator = MagicMock()
    validator.warnings = []
    validator.fix_summary = []
    validator.corrected_spec = None
    monkeypatch.setattr(
        "app.agents.validation.chart_validator.validate_chart_spec",
        lambda spec, data, auto_correct: validator,
    )
    return agents


async def test_history_flows_into_agent_and_turns_persisted(monkeypatch):
    conv = _patch_conversations(
        monkeypatch,
        history=[
            {"role": "user", "content": "total revenue"},
            {"role": "assistant", "content": "It is $1.2M"},
        ],
    )
    agents = _patch_agents(monkeypatch)

    service = ChatService(tenant_id=TENANT)
    response = await service.process_query(
        query="now by region", user_id=USER, roles=["user"], conversation_id=CONV
    )

    # Given conversation_id → no create call; history loaded; turns persisted
    conv.create_conversation.assert_not_awaited()
    conv.list_messages.assert_awaited_once()
    agent_execute = agents["nl2sql"].return_value.execute
    assert agent_execute.call_args.kwargs["history"][0]["content"] == "total revenue"

    roles = [c.kwargs["role"] for c in conv.append_message.await_args_list]
    assert roles == ["user", "assistant"]
    assert conv.append_message.await_args_list[0].kwargs["content"] == "now by region"
    assert conv.append_message.await_args_list[1].kwargs["generated_sql"].startswith("SELECT")
    assert response["conversation_id"] == CONV


async def test_new_conversation_created_when_id_absent(monkeypatch):
    conv = _patch_conversations(monkeypatch, create_returns=CONV)
    _patch_agents(monkeypatch)

    service = ChatService(tenant_id=TENANT)
    response = await service.process_query(query="total revenue", user_id=USER, roles=["user"])

    conv.create_conversation.assert_awaited_once()
    assert conv.create_conversation.await_args.kwargs["title"] == "total revenue"
    assert response["conversation_id"] == CONV


async def test_conversation_create_failure_falls_back(monkeypatch):
    _patch_conversations(monkeypatch, create_returns=None)  # fail-open
    _patch_agents(monkeypatch)

    service = ChatService(tenant_id=TENANT)
    response = await service.process_query(query="total revenue", user_id=USER, roles=["user"])

    # Pipeline still completes with a generated (unpersisted) conversation id
    assert response["conversation_id"]
    assert response["sql"].startswith("SELECT")


async def test_history_load_failure_cold_start(monkeypatch):
    conv = _patch_conversations(monkeypatch)
    conv.list_messages = AsyncMock(side_effect=ConnectionError("db down"))
    agents = _patch_agents(monkeypatch)

    service = ChatService(tenant_id=TENANT)
    events = []
    async for raw in service.process_query_stream(
        query="total revenue", user_id=USER, roles=["user"]
    ):
        events.append(json.loads(raw.removeprefix("data: ").strip()))

    assert events[-1]["status"] == "complete"
    assert events[0]["conversation_id"] == CONV
    agent_execute = agents["nl2sql"].return_value.execute
    assert agent_execute.call_args.kwargs["history"] == []
