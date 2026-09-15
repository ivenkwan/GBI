# SQL Safety Rules

## NEVER generate destructive SQL

All database access through the query engine is READ-ONLY. The following operations are forbidden:

- `DROP TABLE`, `DROP DATABASE`, `DROP SCHEMA`, `DROP INDEX`
- `DELETE FROM`, `TRUNCATE TABLE`
- `ALTER TABLE DROP COLUMN`, `ALTER TABLE RENAME`
- `UPDATE` (unless through explicit service methods with authorization)
- `INSERT` (unless through explicit service methods with authorization)
- `CREATE USER`, `GRANT`, `REVOKE`
- `COPY` (export/import)
- Any multi-statement queries (separated by `;`)

## Always use parameterized queries

- NEVER concatenate user input into SQL strings
- Use SQLAlchemy parameterized queries: `select().where(table.c.name == bindparam("name"))`
- Raw SQL only through `text()` with explicit bind parameters

## Timeout enforcement

- All analytical queries are capped at 30s via `SET statement_timeout = '30s'`
- The ValidationAgent injects this before every query execution

## ValidationAgent must run before every SQL execution

- The ValidationAgent checks for destructive patterns
- It runs a dry-run EXPLAIN plan for cost estimation
- Queries that would scan > 1M rows require explicit user confirmation
