"""BYOK LLM provider endpoints — tenant self-service + admin (Phase 26, ADR 011 §7).

``/settings/llm`` is the tenant's own surface (writes guarded by the tenant
``admin`` role or a platform superuser); ``/admin/tenants/{id}/llm`` is the
superuser force-set/view surface (ADR 009 guards). Every response is masked —
the API key is write-only and can only ever surface as ``key_last4``. Every
mutation is audited by the service layer (actor, tenant, action, key_version).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, require_platform_admin, require_tenant_admin
from app.llm.resolver import BYOKNotConfiguredError

router = APIRouter()


class LLMConfigRequest(BaseModel):
    provider: str = Field(pattern="^(anthropic|openai)$")
    api_key: str = Field(min_length=8, max_length=512)
    base_url: str | None = Field(default=None, max_length=512)
    reasoning_model: str = Field(min_length=1, max_length=100)
    fast_model: str = Field(min_length=1, max_length=100)
    embedding_model: str | None = Field(default=None, max_length=100)


class LLMStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")


class LLMConfigOut(BaseModel):
    configured: bool
    provider: str | None = None
    base_url: str | None = None
    reasoning_model: str | None = None
    fast_model: str | None = None
    embedding_model: str | None = None
    key_last4: str | None = None
    key_version: int | None = None
    status: str | None = None
    updated_at: str | None = None


class LLMUsageRow(BaseModel):
    day: str
    provider: str | None = None
    key_source: str | None = None
    model_name: str
    calls: int
    input_tokens: int
    output_tokens: int


class TenantLLMOut(BaseModel):
    config: LLMConfigOut
    usage: list[LLMUsageRow]


def _config_out(config: dict | None) -> LLMConfigOut:
    if not config:
        return LLMConfigOut(configured=False)
    return LLMConfigOut(configured=True, **config)


def _byok_error(e: Exception) -> HTTPException:
    from app.services.byok import BYOKValidationError

    if isinstance(e, BYOKValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BYOK_VALIDATION_FAILED", "message": str(e)},
        )
    if isinstance(e, BYOKNotConfiguredError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "BYOK_NOT_CONFIGURED", "message": str(e)},
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "CONTROL_PLANE_UNAVAILABLE",
            "message": f"BYOK store unavailable: {type(e).__name__}",
        },
    )


def _save_config(tenant_id: str, request: LLMConfigRequest, actor_user_id: str) -> dict:
    """Shared PUT body for the tenant and admin force-set paths."""
    from app.services.byok import set_provider_config

    return set_provider_config(
        tenant_id=tenant_id,
        provider=request.provider,
        api_key=request.api_key,
        reasoning_model=request.reasoning_model,
        fast_model=request.fast_model,
        embedding_model=request.embedding_model,
        base_url=request.base_url or None,
        actor_user_id=actor_user_id,
    )


# ---------------------------------------------------------------------------
# Tenant self-service: /settings/llm
# ---------------------------------------------------------------------------


@router.get("/settings/llm", response_model=LLMConfigOut)
async def get_llm_config(user: dict = Depends(get_current_user)):
    """The tenant's own LLM config, masked (the key never leaves the DB)."""
    from app.services.byok import get_provider_config

    try:
        return _config_out(await get_provider_config(str(user["tenant_id"])))
    except Exception as e:
        raise _byok_error(e) from None


@router.put("/settings/llm", response_model=LLMConfigOut)
async def put_llm_config(
    request: LLMConfigRequest,
    user: dict = Depends(require_tenant_admin),
):
    """Create/replace the tenant's BYOK config — validated live, then saved."""
    try:
        saved = await _save_config(str(user["tenant_id"]), request, str(user["sub"]))
    except Exception as e:
        raise _byok_error(e) from None
    return _config_out(saved)


@router.post("/settings/llm/validate")
async def validate_llm_config(
    request: LLMConfigRequest,
    user: dict = Depends(require_tenant_admin),
):
    """Live 1-token ping against the provider — nothing is saved."""
    from app.services.byok import validate_provider

    try:
        await validate_provider(
            request.provider, request.api_key, request.base_url or None, request.fast_model
        )
    except Exception as e:
        raise _byok_error(e) from None
    return {"status": "ok", "provider": request.provider}


@router.patch("/settings/llm", response_model=LLMConfigOut)
async def patch_llm_status(
    request: LLMStatusRequest,
    user: dict = Depends(require_tenant_admin),
):
    """active/disabled kill switch — ``disabled`` is the explicit revert."""
    from app.services.byok import get_provider_config, set_status

    tenant_id = str(user["tenant_id"])
    try:
        updated = await set_status(tenant_id, request.status, actor_user_id=str(user["sub"]))
        if not updated:
            raise KeyError("no config row")
        return _config_out(await get_provider_config(tenant_id))
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NO_LLM_CONFIG", "message": "No BYOK config for this tenant"},
        ) from None
    except Exception as e:
        raise _byok_error(e) from None


@router.delete("/settings/llm")
async def delete_llm_config(user: dict = Depends(require_tenant_admin)):
    """Remove the config — LLM calls revert to the platform key."""
    from app.services.byok import delete_provider_config

    try:
        deleted = await delete_provider_config(
            str(user["tenant_id"]), actor_user_id=str(user["sub"])
        )
    except Exception as e:
        raise _byok_error(e) from None
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NO_LLM_CONFIG", "message": "No BYOK config for this tenant"},
        ) from None
    return {"status": "reverted", "provider": "platform"}


# ---------------------------------------------------------------------------
# Admin (platform superuser): /admin/tenants/{id}/llm
# ---------------------------------------------------------------------------


def _tenant_id_or_400(tenant_id: str) -> str:
    try:
        return str(uuid.UUID(tenant_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TENANT", "message": "Not a valid tenant id"},
        ) from None


@router.get("/admin/tenants/{tenant_id}/llm", response_model=TenantLLMOut)
async def get_tenant_llm(
    tenant_id: str,
    user: dict = Depends(require_platform_admin),
    days: int = Query(default=7, ge=1, le=90, description="Spend attribution window"),
):
    """Masked tenant config + spend attribution from the audit trail."""
    from app.services.byok import get_provider_config, tenant_llm_usage

    scope = _tenant_id_or_400(tenant_id)
    try:
        config = await get_provider_config(scope)
        usage = await tenant_llm_usage(scope, days)
    except Exception as e:
        raise _byok_error(e) from None
    return TenantLLMOut(
        config=_config_out(config),
        usage=[LLMUsageRow(**row) for row in usage],
    )


@router.put("/admin/tenants/{tenant_id}/llm", response_model=LLMConfigOut)
async def put_tenant_llm(
    tenant_id: str,
    request: LLMConfigRequest,
    user: dict = Depends(require_platform_admin),
):
    """Force-set a tenant's BYOK config on its behalf (validated + audited)."""
    scope = _tenant_id_or_400(tenant_id)
    try:
        saved = await _save_config(scope, request, str(user["sub"]))
    except Exception as e:
        raise _byok_error(e) from None
    return _config_out(saved)


@router.patch("/admin/tenants/{tenant_id}/llm", response_model=LLMConfigOut)
async def patch_tenant_llm_status(
    tenant_id: str,
    request: LLMStatusRequest,
    user: dict = Depends(require_platform_admin),
):
    """Superuser status toggle — disabled reverts the tenant to the platform key."""
    from app.services.byok import get_provider_config, set_status

    scope = _tenant_id_or_400(tenant_id)
    try:
        updated = await set_status(scope, request.status, actor_user_id=str(user["sub"]))
        if not updated:
            raise KeyError("no config row")
        return _config_out(await get_provider_config(scope))
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NO_LLM_CONFIG", "message": "No BYOK config for this tenant"},
        ) from None
    except Exception as e:
        raise _byok_error(e) from None
