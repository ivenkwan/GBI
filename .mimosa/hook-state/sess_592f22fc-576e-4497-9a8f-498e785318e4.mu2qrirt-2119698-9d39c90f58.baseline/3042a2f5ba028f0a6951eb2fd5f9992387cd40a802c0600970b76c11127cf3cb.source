"""Phase 24 pipeline wiring: Tenant Knowledge prompt section, wiki retrieval
into NL2SQL (fail-open), and the chat_knowledge intent short-circuit."""

from unittest.mock import AsyncMock, MagicMock

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"

WIKI_HITS = [
    {"slug": "glossary", "title": "Glossary", "chunk": "qualified pipeline means", "score": 0.9}
]


def test_build_user_message_knowledge_section():
    from app.agents.nl2sql.nl2sql_agent import NL2SQLAgent

    agent = NL2SQLAgent.__new__(NL2SQLAgent)  # prompt build is pure
    message = agent._build_user_message(
        query="revenue by qualified pipeline",
        schema_context=None,
        few_shot_examples=None,
        metric_definitions=None,
        tenant_id=TENANT,
        tenant_knowledge=WIKI_HITS,
    )
    assert "## Tenant Knowledge" in message
    assert "`glossary`" in message and "qualified pipeline means" in message

    without = agent._build_user_message(
        query="q",
        schema_context=None,
        few_shot_examples=None,
        metric_definitions=None,
        tenant_id=TENANT,
        tenant_knowledge=None,
    )
    assert "Tenant Knowledge" not in without


def _pipeline_cache(monkeypatch, wiki_hits=None):
    """Cache mock matching the pipeline's reads; wiki channel scriptable."""
    import app.services.chat_service as cs

    cache = MagicMock()
    cache.get_metric_definitions = AsyncMock(return_value="")
    cache.get_schema_context = AsyncMock(return_value=[])
    cache.get_few_shot_examples = AsyncMock(return_value=[])
    cache.get_query_result = AsyncMock(return_value=[])
    cache.get_wiki_context = AsyncMock(return_value=wiki_hits)
    cache.set_wiki_context = AsyncMock()
    monkeypatch.setattr(cs, "get_cache", lambda: cache)
    return cache


async def test_chat_pipeline_reads_and_caches_wiki_context(monkeypatch):
    """Wiring contract: on a cache miss the pipeline retrieves the wiki
    context for (query, tenant) and caches it — that value is exactly what
    _step_nl2sql forwards as tenant_knowledge."""
    from app.services.chat_service import ChatService
    from tests.services.test_chat_pipeline import _patch_pipeline

    _patch_pipeline(monkeypatch)
    cache = _pipeline_cache(monkeypatch, wiki_hits=None)  # miss on first read

    wiki = MagicMock()
    wiki.retrieve_wiki_context = AsyncMock(return_value=WIKI_HITS)
    monkeypatch.setattr("app.services.wiki.retrieve_wiki_context", wiki.retrieve_wiki_context)

    service = ChatService(tenant_id=TENANT)
    response = await service.process_query(query="pipeline question", user_id=USER, roles=["user"])

    wiki.retrieve_wiki_context.assert_awaited_once_with("pipeline question", TENANT, top_k=3)
    cache.set_wiki_context.assert_awaited_once_with("pipeline question", TENANT, WIKI_HITS)
    assert response["conversation_id"]  # pipeline completed (no-data exit is fine)

    # On a hit the retrieval is skipped and the cached value is used —
    # this is the value _step_nl2sql passes through to the agent.
    wiki.retrieve_wiki_context.reset_mock()
    cache.get_wiki_context = AsyncMock(return_value=WIKI_HITS)
    await service.process_query(query="pipeline question", user_id=USER, roles=["user"])
    wiki.retrieve_wiki_context.assert_not_awaited()


async def test_chat_pipeline_wiki_retrieval_fail_open(monkeypatch):
    from app.services.chat_service import ChatService
    from tests.services.test_chat_pipeline import _patch_pipeline

    _patch_pipeline(monkeypatch)
    cache = _pipeline_cache(monkeypatch)
    cache.get_wiki_context = AsyncMock(side_effect=RuntimeError("cache down"))

    service = ChatService(tenant_id=TENANT)
    response = await service.process_query(query="q", user_id=USER, roles=["user"])
    assert response["conversation_id"]  # pipeline completed despite the outage


async def test_chat_knowledge_intent_short_circuits(monkeypatch):
    from app.services.chat_service import ChatService
    from tests.services.test_chat_pipeline import _patch_pipeline

    _patch_pipeline(monkeypatch, router_output={"intent": "chat_knowledge", "dispatch_plan": []})
    _pipeline_cache(monkeypatch)

    wiki = MagicMock()
    wiki.retrieve_wiki_context = AsyncMock(return_value=WIKI_HITS)
    monkeypatch.setattr("app.services.wiki.retrieve_wiki_context", wiki.retrieve_wiki_context)

    llm = MagicMock()
    llm.invoke = AsyncMock(
        return_value=MagicMock(content="A qualified pipeline means X (page: glossary)")
    )
    monkeypatch.setattr("app.core.llm_client.get_llm_client", lambda: llm)

    # The SQL step must never run: make any connector creation explode.
    import app.connectors.postgresql_connector as pgc

    monkeypatch.setattr(
        pgc, "PostgreSQLConnector", MagicMock(side_effect=AssertionError("SQL path must not run"))
    )

    service = ChatService(tenant_id=TENANT)
    response = await service.process_query(
        query="what is a qualified pipeline?", user_id=USER, roles=["user"]
    )

    assert response["narrative"].startswith("A qualified pipeline")
    assert response["sql"] is None
    assert response["chart_spec"] is None


async def test_chat_knowledge_no_hits_falls_through(monkeypatch):
    from app.services.chat_service import ChatService
    from tests.services.test_chat_pipeline import _patch_pipeline

    _patch_pipeline(monkeypatch, router_output={"intent": "chat_knowledge", "dispatch_plan": []})
    _pipeline_cache(monkeypatch)

    wiki = MagicMock()
    wiki.retrieve_wiki_context = AsyncMock(return_value=[])
    monkeypatch.setattr("app.services.wiki.retrieve_wiki_context", wiki.retrieve_wiki_context)

    service = ChatService(tenant_id=TENANT)
    response = await service.process_query(query="what is x?", user_id=USER, roles=["user"])
    assert response["sql"]  # fell through to the data pipeline
