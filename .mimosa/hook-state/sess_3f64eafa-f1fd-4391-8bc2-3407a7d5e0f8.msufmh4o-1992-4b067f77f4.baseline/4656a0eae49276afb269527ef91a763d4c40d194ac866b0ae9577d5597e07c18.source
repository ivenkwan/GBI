# API Design Standards

## Route conventions

- ALL API routes are versioned under `/api/v1/`
- Route files are `snake_case.py` in `backend/app/api/v1/`

## Request/Response schema

- Every request body is a Pydantic v2 model with `extra="forbid"`
- Every response body is a Pydantic v2 model
- Error responses use: `{"detail": {"code": "ERROR_CODE", "message": "Human-readable message"}}`

## Async everywhere

- All FastAPI route handlers are `async def`
- All DB calls use async SQLAlchemy (`async_session` with `asyncpg`)

## Dependency injection

- Auth/session/db always via FastAPI `Depends()` — never instantiated in route body
- `user: dict = Depends(get_current_user)` for auth
- `db: AsyncSession = Depends(get_db)` for database

## Streaming

- SSE endpoints return `StreamingResponse` with media_type `text/event-stream`
- Each event is: `data: {json}\n\n`

## CORS

- Configured via `settings.CORS_ORIGINS`
- In development: `["http://localhost:3000"]`
- In production: strict origin list
