"""Unit tests for the embedding provider (app.core.embeddings)."""

from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.core.embeddings import embed_text, vector_literal


class _FakeEmbeddings:
    def __init__(self, vector):
        self._vector = vector

    async def create(self, model, input, dimensions):
        return SimpleNamespace(data=[SimpleNamespace(embedding=self._vector)])


async def test_embed_text_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await embed_text("hello")


async def test_embed_text_returns_vector(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    vector = [0.1] * settings.EMBEDDING_DIMS
    monkeypatch.setattr(
        "openai.AsyncOpenAI",
        lambda api_key=None: SimpleNamespace(embeddings=_FakeEmbeddings(vector)),
    )

    result = await embed_text("total revenue by region")
    assert result == vector


async def test_embed_text_rejects_wrong_dims(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "openai.AsyncOpenAI",
        lambda api_key=None: SimpleNamespace(embeddings=_FakeEmbeddings([0.1] * 7)),
    )

    with pytest.raises(RuntimeError, match="dims"):
        await embed_text("hello")


async def test_embed_text_wraps_api_errors(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    class Boom:
        async def create(self, **kwargs):
            raise ValueError("api down")

    monkeypatch.setattr(
        "openai.AsyncOpenAI", lambda api_key=None: SimpleNamespace(embeddings=Boom())
    )

    with pytest.raises(RuntimeError, match="embedding API call failed"):
        await embed_text("hello")


def test_vector_literal_format():
    assert vector_literal([0.5, -0.25]) == "[0.5,-0.25]"
