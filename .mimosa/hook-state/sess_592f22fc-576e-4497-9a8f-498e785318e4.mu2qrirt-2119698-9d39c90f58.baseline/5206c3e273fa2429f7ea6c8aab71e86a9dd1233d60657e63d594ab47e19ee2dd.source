"""Wiki endpoints — tenant knowledge base (Phase 24, ADR 010).

Reads: any authenticated tenant user. Writes: tenant ``admin`` role or
platform superuser — 403 WIKI_READ_ONLY for everyone else (guard inside each write handler).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter()

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,199}$")


class PageUpsertRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content_md: str = Field(min_length=1, max_length=200_000)
    parent_slug: str | None = Field(default=None, max_length=200)


class PageOut(BaseModel):
    slug: str
    title: str
    content_md: str
    parent_slug: str | None = None
    updated_by: str
    updated_at: str
    created_at: str
    version: int | None = None
    embedded: bool | None = None


class PageSummaryOut(BaseModel):
    slug: str
    title: str
    parent_slug: str | None = None
    updated_at: str


class RevisionOut(BaseModel):
    version: int
    title: str
    edited_by: str
    created_at: str


class SearchHitOut(BaseModel):
    slug: str
    title: str
    chunk: str
    score: float


def _valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug))


def _write_guard(user: dict):
    """A plain user passing the guard dependency still gets the wiki-specific
    code (WIKI_READ_ONLY) rather than the generic NOT_TENANT_ADMIN."""
    roles = user.get("roles") or []
    if "admin" not in roles and user.get("platform_admin"):
        # Platform superusers without the tenant role: allow (ADR 010 §1)
        return
    if "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "WIKI_READ_ONLY",
                "message": "Only tenant admins may edit the knowledge base",
            },
        )


@router.get("", response_model=list[PageSummaryOut])
async def list_pages(user: dict = Depends(get_current_user)):
    """The tenant's pages (tree assembly happens in the client)."""
    from app.services.wiki import list_pages as list_all

    try:
        rows = await list_all(user["tenant_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WIKI_UNAVAILABLE",
                "message": f"Knowledge base unavailable: {type(e).__name__}",
            },
        ) from None
    return [PageSummaryOut(**r) for r in rows]


@router.get("/search", response_model=list[SearchHitOut])
async def search_wiki(
    user: dict = Depends(get_current_user),
    q: str = Query(min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=20),
):
    """Semantic search over the tenant's wiki (keyword fallback)."""
    from app.services.wiki import search_pages

    hits = await search_pages(q, user["tenant_id"], top_k=top_k)
    return [SearchHitOut(**h) for h in hits]


@router.get("/{slug}", response_model=PageOut)
async def get_page(slug: str, user: dict = Depends(get_current_user)):
    """One page (markdown)."""
    from app.services.wiki import get_page as get_one

    if not _valid_slug(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SLUG",
                "message": "Slugs are lowercase letters, digits, hyphens",
            },
        )
    try:
        page = await get_one(user["tenant_id"], slug)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WIKI_UNAVAILABLE",
                "message": f"Knowledge base unavailable: {type(e).__name__}",
            },
        ) from None
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PAGE_NOT_FOUND", "message": "No such page"},
        )
    return PageOut(**page)


@router.put("/{slug}", response_model=PageOut)
async def upsert_page(
    slug: str,
    request: PageUpsertRequest,
    user: dict = Depends(get_current_user),
):
    """Create or update a page — appends a revision atomically."""
    from app.services.wiki import PageExistsError
    from app.services.wiki import upsert_page as upsert

    _write_guard(user)
    if not _valid_slug(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SLUG",
                "message": "Slugs are lowercase letters, digits, hyphens",
            },
        )
    try:
        page = await upsert(
            tenant_id=user["tenant_id"],
            slug=slug,
            title=request.title,
            content_md=request.content_md,
            editor_user_id=str(user["sub"]),
            parent_slug=request.parent_slug,
        )
    except PageExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "SLUG_CONFLICT", "message": str(e)},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WIKI_UNAVAILABLE",
                "message": f"Knowledge base unavailable: {type(e).__name__}",
            },
        ) from None
    return PageOut(**page)


@router.delete("/{slug}")
async def delete_page(slug: str, user: dict = Depends(get_current_user)):
    """Delete a page and its history. 404 when not found."""
    from app.services.wiki import delete_page as delete_one

    _write_guard(user)
    if not _valid_slug(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SLUG",
                "message": "Slugs are lowercase letters, digits, hyphens",
            },
        )
    try:
        deleted = await delete_one(user["tenant_id"], slug)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WIKI_UNAVAILABLE",
                "message": f"Knowledge base unavailable: {type(e).__name__}",
            },
        ) from None
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PAGE_NOT_FOUND", "message": "No such page"},
        )
    return {"status": "deleted", "slug": slug}


@router.get("/{slug}/history", response_model=list[RevisionOut])
async def page_history(slug: str, user: dict = Depends(get_current_user)):
    """Revisions newest-first. 404 when the page does not exist."""
    from app.services.wiki import page_history as history

    try:
        revisions = await history(user["tenant_id"], slug)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WIKI_UNAVAILABLE",
                "message": f"Knowledge base unavailable: {type(e).__name__}",
            },
        ) from None
    if revisions is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PAGE_NOT_FOUND", "message": "No such page"},
        )
    return [RevisionOut(**r) for r in revisions]


@router.post("/{slug}/restore/{version}", response_model=PageOut)
async def restore_page(
    slug: str,
    version: int,
    user: dict = Depends(get_current_user),
):
    """Restore an old revision FORWARD as a new revision (history is
    append-only)."""
    from app.services.wiki import restore_page as restore

    _write_guard(user)
    if not _valid_slug(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SLUG",
                "message": "Slugs are lowercase letters, digits, hyphens",
            },
        )
    try:
        page = await restore(
            tenant_id=user["tenant_id"],
            slug=slug,
            version=version,
            editor_user_id=str(user["sub"]),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WIKI_UNAVAILABLE",
                "message": f"Knowledge base unavailable: {type(e).__name__}",
            },
        ) from None
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REVISION_NOT_FOUND", "message": "No such page or version"},
        )
    return PageOut(**page)
