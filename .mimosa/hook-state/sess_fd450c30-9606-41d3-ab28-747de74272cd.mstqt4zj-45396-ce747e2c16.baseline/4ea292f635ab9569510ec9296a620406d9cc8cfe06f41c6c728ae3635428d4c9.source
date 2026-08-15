"""Tests for pgvector schema/few-shot retrieval (app.services.schema_retrieval).

Everything is mocked: the embedding call and the read data source (standard
unittest.mock doubles). These tests pin the retrieval contract: tenant
threading (RLS GUC), vector parameter format, result mapping, and the
fail-open behavior.
"""

import json
from unittest.mock import AsyncMock, MagicMock

from app.services import schema_retrieval
from app.services.schema_retrieval import (
    retrieve_few_shot_examples,
    retrieve_schema_context,
)

TENANT = "00000000-0000-0000-0000-000000000001"


def _patch_embedding(monkeypatch, vector=None, error=None):
    async def fake_embed(text):
        if error:
            raise error
        return vector or [0.1] * 8

    monkeypatch.setattr(schema_retrieval, "embed_text", fake_embed)


def _make_source(monkeypatch, rows):
    """Patch in a mock data source; returns (source, factory)."""
    source = MagicMock()
    source.execute = AsyncMock(return_value=rows)
    factory = MagicMock(return_value=source)
    monkeypatch.setattr("app.connectors.postgresql_connector.PostgreSQLConnector", factory)
    return source, factory


async def test_schema_retrieval_tenant_scoping_and_mapping(monkeypatch):
    _patch_embedding(monkeypatch, vector=[0.25] * 8)
    rows = [
        {
            "full_name": "public.sales",
            "table_description": "Sales transactions",
            "columns_json": [{"column_name": "region", "data_type": "character varying"}],
            "score": 0.92,
        }
    ]
    source, factory = _make_source(monkeypatch, rows)

    context = await retrieve_schema_context("revenue by region", TENANT, top_k=5)

    # The read ran scoped to the tenant (drives the RLS GUC) with a
    # vector-literal parameter and the requested top_k.
    assert factory.call_args.kwargs["tenant_id"] == TENANT
    params = source.execute.call_args.kwargs["params"]
    assert params["top_k"] == 5
    assert params["emb"].startswith("[")
    assert params["emb"].endswith("]")

    # Mapping matches NL2SQLAgent._build_user_message's expected shape
    assert context == [
        {
            "table_name": "public.sales",
            "description": "Sales transactions",
            "columns": [{"column_name": "region", "data_type": "character varying"}],
        }
    ]


async def test_schema_retrieval_parses_string_columns_json(monkeypatch):
    _patch_embedding(monkeypatch)
    rows = [
        {
            "full_name": "public.orders",
            "table_description": "",
            "columns_json": json.dumps([{"column_name": "status"}]),
            "score": 0.8,
        }
    ]
    _make_source(monkeypatch, rows)

    context = await retrieve_schema_context("order status", TENANT)
    assert context[0]["columns"] == [{"column_name": "status"}]


async def test_schema_retrieval_fails_open(monkeypatch):
    _patch_embedding(monkeypatch, error=RuntimeError("no key"))

    assert await retrieve_schema_context("anything", TENANT) == []


async def test_few_shot_retrieval_tenant_scoping_and_mapping(monkeypatch):
    _patch_embedding(monkeypatch)
    rows = [
        {
            "nl_query": "Show me total revenue by region",
            "expected_sql": "<revenue-by-region-query>",
            "score": 0.9,
        }
    ]
    source, factory = _make_source(monkeypatch, rows)

    examples = await retrieve_few_shot_examples("revenue by region", TENANT, top_k=3)

    assert factory.call_args.kwargs["tenant_id"] == TENANT
    assert source.execute.call_args.kwargs["params"]["top_k"] == 3
    assert examples == [
        {
            "nl_query": "Show me total revenue by region",
            "expected_sql": "<revenue-by-region-query>",
        }
    ]


async def test_few_shot_retrieval_fails_open(monkeypatch):
    _patch_embedding(monkeypatch, error=RuntimeError("api down"))

    assert await retrieve_few_shot_examples("anything", TENANT) == []
