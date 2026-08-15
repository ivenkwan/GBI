"""Phase 15 governance tests: feedback API + per-role validation."""

import uuid
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from app.agents.base import AgentConfig
from app.agents.validation.validation_agent import ValidationAgent
from app.core.auth import create_access_token

TENANT = "00000000-0000-0000-0000-000000000001"
SESSION = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Per-role validation
# ---------------------------------------------------------------------------


def _agent() -> ValidationAgent:
    return ValidationAgent(AgentConfig(model_name="deterministic"))


async def test_recognized_role_allows_query():
    result = await _agent().execute(
        sql="SELECT region, revenue FROM public.sales GROUP BY region",
        user_roles=["user"],
    )
    assert result.success is True


async def test_unrecognized_role_rejected():
    result = await _agent().execute(
        sql="SELECT region FROM public.sales",
        user_roles=["billing-only"],
    )
    assert result.success is False
    assert any("not authorized to run queries" in e for e in result.errors)


async def test_viewer_role_rejects_joins():
    result = await _agent().execute(
        sql="SELECT r.region_name, s.revenue FROM public.sales s "
        "JOIN public.regions r ON s.region = r.region_name",
        user_roles=["viewer"],
    )
    assert result.success is False
    assert any("viewer role" in e for e in result.errors)


async def test_viewer_role_allows_single_table():
    result = await _agent().execute(
        sql="SELECT region, revenue FROM public.sales WHERE region = 'North'",
        user_roles=["viewer"],
    )
    assert result.success is True


async def test_empty_roles_unrestricted():
    """No roles passed (tests, internal calls) — the connector and RLS
    remain the hard gates; the role check is a policy layer on top."""
    result = await _agent().execute(
        sql="SELECT region FROM public.sales JOIN public.regions ON TRUE",
    )
    # JOIN is fine with no roles; the policy only restricts the viewer role
    assert result.success is True


# ---------------------------------------------------------------------------
# Feedback endpoint
# ---------------------------------------------------------------------------


async def _post_feedback(json_body, headers=None):
    from app.main import create_app

    app = create_app()
    if headers is None:
        token = create_access_token(user_id="test-user", tenant_id=TENANT)
        headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/chat/feedback", json=json_body, headers=headers)


def _patch_record_feedback(monkeypatch, returns=True):
    from app.services import audit as audit_module

    mock = AsyncMock(return_value=returns)
    monkeypatch.setattr(audit_module, "record_feedback", mock)
    return mock


async def test_feedback_records(monkeypatch):
    mock = _patch_record_feedback(monkeypatch)

    res = await _post_feedback({"session_id": SESSION, "score": 1})

    assert res.status_code == 200
    assert res.json()["status"] == "recorded"
    mock.assert_awaited_once_with(session_id=SESSION, tenant_id=TENANT, score=1)


async def test_feedback_503_when_recording_fails(monkeypatch):
    _patch_record_feedback(monkeypatch, returns=False)

    res = await _post_feedback({"session_id": SESSION, "score": -1})

    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "FEEDBACK_UNAVAILABLE"


async def test_feedback_validates_score(monkeypatch):
    _patch_record_feedback(monkeypatch)

    res = await _post_feedback({"session_id": SESSION, "score": 5})

    assert res.status_code == 422


async def test_feedback_requires_auth(monkeypatch):
    _patch_record_feedback(monkeypatch)

    res = await _post_feedback({"session_id": SESSION, "score": 1}, headers={})

    assert res.status_code in (401, 403)
