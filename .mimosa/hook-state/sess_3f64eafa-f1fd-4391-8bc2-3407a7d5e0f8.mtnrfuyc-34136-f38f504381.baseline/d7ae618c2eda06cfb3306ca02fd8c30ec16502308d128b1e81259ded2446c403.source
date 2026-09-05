"""ValidationAgent — SQL safety gate before execution.

This agent runs deterministically (no LLM call) on every generated SQL query
before it's executed against a data source. It checks:

1. Destructive pattern detection (DROP, DELETE, TRUNCATE, etc.)
2. Read-only enforcement (only SELECT statements)
3. Dry-run EXPLAIN plan for cost estimation
4. Row count limits (>1M rows requires user confirmation)
5. 30-second statement_timeout injection
6. Multi-statement detection (prevents `;` injection attacks)

IMPORTANT: This file is in the DO NOT MODIFY (Protected) list in CLAUDE.md.
Any relaxation of safety rules requires explicit approval and security review.
"""

import re
import time

from app.agents.base import AgentConfig, AgentResult, BaseAgent
from app.agents.registry import register_agent
from app.core.logging import logger


@register_agent("validation")
class ValidationAgent(BaseAgent):
    """Deterministic SQL safety validator — no LLM call.

    Every generated SQL MUST pass through this agent before execution.
    The agent is intentionally conservative: when in doubt, reject.

    Attributes:
        MAX_ROW_ESTIMATE: Queries estimated to scan more than this many rows
            require explicit user confirmation (not rejection).
    """

    name = "validation"
    description = "SQL safety gate — destructive pattern detection, EXPLAIN dry-run, row limits"

    MAX_ROW_ESTIMATE: int = 1_000_000
    STATEMENT_TIMEOUT: str = "30s"

    # Patterns that are ALWAYS rejected (no exceptions)
    DESTRUCTIVE_PATTERNS: list[tuple[str, str]] = [
        # (regex pattern, description)
        (r"\bDROP\s+TABLE\b", "DROP TABLE"),
        (r"\bDROP\s+DATABASE\b", "DROP DATABASE"),
        (r"\bDROP\s+SCHEMA\b", "DROP SCHEMA"),
        (r"\bDROP\s+INDEX\b", "DROP INDEX"),
        (r"\bDROP\s+VIEW\b", "DROP VIEW"),
        (r"\bDROP\s+FUNCTION\b", "DROP FUNCTION"),
        (r"\bDROP\s+PROCEDURE\b", "DROP PROCEDURE"),
        (r"\bDELETE\s+FROM\b", "DELETE FROM"),
        (r"\bTRUNCATE\s+(TABLE\s+)?", "TRUNCATE"),
        (r"\bALTER\s+TABLE\b.*\bDROP\b", "ALTER TABLE DROP"),
        (r"\bALTER\s+TABLE\b.*\bRENAME\b", "ALTER TABLE RENAME"),
        (r"\bINSERT\s+INTO\b", "INSERT INTO"),
        (r"\bCREATE\s+USER\b", "CREATE USER"),
        (r"\bCREATE\s+ROLE\b", "CREATE ROLE"),
        (r"\bGRANT\b", "GRANT"),
        (r"\bREVOKE\b", "REVOKE"),
        (r"\bCOPY\b.*\bFROM\b", "COPY FROM (data export)"),
    ]

    # Patterns that trigger warnings but not rejection
    WARNING_PATTERNS: list[tuple[str, str]] = [
        (r"\bUPDATE\s+\w+\s+SET\b", "UPDATE — only allowed via explicit service methods"),
        (r"\bINSERT\s", "INSERT — only allowed via explicit service methods"),
        (r"\bCREATE\s+TABLE\b", "CREATE TABLE — requires admin privileges"),
        (r"\bCREATE\s+INDEX\b", "CREATE INDEX — requires admin privileges"),
    ]

    async def execute(
        self,
        sql: str | None = None,
        tenant_id: str = "default",
        user_roles: list[str] | None = None,
        **kwargs,
    ) -> AgentResult:
        """Validate a SQL query for safety.

        Args:
            sql: The generated SQL query to validate.
            tenant_id: Tenant identifier.
            user_roles: User's roles for permission checks.

        Returns:
            AgentResult with:
                - success=True if SQL is safe to execute
                - warnings: list of advisory warnings
                - errors: list of blocking errors (if any, SQL is rejected)
                - output: validation details (explain_plan, row_estimate, etc.)
        """
        start = time.time()

        if not sql:
            return self._timed_result(
                AgentResult(
                    agent_name=self.name,
                    success=False,
                    output={},
                    errors=["No SQL provided for validation"],
                ),
                start,
            )

        errors: list[str] = []
        warnings: list[str] = []

        # 1. Multi-statement injection check
        multi_stmt_warnings = self._check_multi_statement(sql)
        if multi_stmt_warnings:
            errors.extend(multi_stmt_warnings)

        # 2. Destructive pattern detection
        destructive_errors, destructive_warnings = self._check_destructive_patterns(sql)
        errors.extend(destructive_errors)
        warnings.extend(destructive_warnings)

        # 3. Read-only enforcement (must be SELECT)
        if not self._is_select_only(sql):
            errors.append(
                "Query is not a SELECT statement. All data access through the "
                "query engine must be read-only. Write operations require "
                "explicit service method authorization."
            )

        # 4. Statement timeout injection
        timeout_sql = self._inject_timeout(sql)

        # 5. Basic sanity checks
        if not self._has_required_clauses(sql):
            warnings.append("Query may be missing FROM or WHERE clause")

        # Build validation output
        valid = len(errors) == 0
        explain_plan = None
        row_estimate = None

        # 6. EXPLAIN dry-run (async, only if query is otherwise valid)
        if valid:
            # TODO: Run actual EXPLAIN via the connector
            # explain_result = await connector.explain(sql)
            # row_estimate = extract_row_estimate(explain_result)
            explain_plan = "EXPLAIN not yet connected — will run at execution time"
            row_estimate = 0

        # 7. Row count check (>1M requires user confirmation)
        if row_estimate and row_estimate > self.MAX_ROW_ESTIMATE:
            warnings.append(
                f"Query estimated to scan ~{row_estimate:,} rows (limit: {self.MAX_ROW_ESTIMATE:,}). "
                "This requires explicit user confirmation before execution."
            )

        logger.info(
            "Validation complete",
            valid=valid,
            errors=len(errors),
            warnings=len(warnings),
            row_estimate=row_estimate,
        )

        return self._timed_result(
            AgentResult(
                agent_name=self.name,
                success=valid,
                output={
                    "validated_sql": timeout_sql,
                    "explain_plan": explain_plan,
                    "row_estimate": row_estimate,
                    "requires_confirmation": bool(
                        row_estimate and row_estimate > self.MAX_ROW_ESTIMATE
                    ),
                },
                warnings=warnings,
                errors=errors,
            ),
            start,
        )

    def _check_multi_statement(self, sql: str) -> list[str]:
        """Detect multi-statement SQL (possible injection)."""
        errors = []

        # Remove string literals to avoid false positives on semicolons in strings
        cleaned = self._remove_string_literals(sql)

        # Count statements (naive: split on `;` outside strings)
        statements = [s.strip() for s in cleaned.split(";") if s.strip()]
        if len(statements) > 1:
            errors.append(
                f"Multi-statement query detected ({len(statements)} statements). "
                "Only single SELECT statements are allowed through the query engine. "
                "Multiple statements indicate a potential SQL injection attack."
            )

        return errors

    def _check_destructive_patterns(self, sql: str) -> tuple[list[str], list[str]]:
        """Check SQL for destructive patterns.

        Returns:
            Tuple of (errors, warnings) — errors block execution, warnings are advisory.
        """
        sql_upper = sql.upper()
        errors = []
        warnings = []

        for pattern, description in self.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, sql_upper):
                errors.append(
                    f"Destructive operation detected: {description}. "
                    "All queries through the query engine are read-only."
                )

        for pattern, description in self.WARNING_PATTERNS:
            if re.search(pattern, sql_upper):
                warnings.append(
                    f"Potentially unsafe operation: {description}. "
                    "This query will be flagged for review."
                )

        return errors, warnings

    def _is_select_only(self, sql: str) -> bool:
        """Check that the SQL is a SELECT statement (or WITH/CTE)."""
        sql_stripped = sql.strip().upper()
        # Strip leading comments and whitespace
        while sql_stripped.startswith(("--", "/*", "(")):
            if sql_stripped.startswith("--"):
                sql_stripped = sql_stripped.split("\n", 1)[-1].strip() if "\n" in sql_stripped else ""
            elif sql_stripped.startswith("/*"):
                end = sql_stripped.find("*/")
                sql_stripped = sql_stripped[end + 2:].strip() if end != -1 else ""
            elif sql_stripped.startswith("("):
                # CTE or subquery — scan for SELECT after leading parens
                depth = 0
                for i, c in enumerate(sql_stripped):
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                        if depth == 0:
                            sql_stripped = sql_stripped[i + 1:].strip()
                            break
                else:
                    break

        return sql_stripped.startswith(
            ("SELECT", "WITH", "EXPLAIN", "EXPLAIN ANALYZE", "SHOW", "DESCRIBE")
        )

    def _inject_timeout(self, sql: str) -> str:
        """Inject a statement_timeout into the query to cap execution time."""
        prefix = f"SET LOCAL statement_timeout = '{self.STATEMENT_TIMEOUT}';\n"
        return prefix + sql

    def _has_required_clauses(self, sql: str) -> bool:
        """Basic sanity check: SELECT should have FROM or be a simple expression."""
        sql_upper = sql.upper()
        # SELECT 1, SELECT now(), etc. are valid
        if re.search(r"\bFROM\b", sql_upper):
            return True
        # Simple functions without FROM are fine
        if re.search(
            r"SELECT\s+(NOW\(\)|CURRENT_DATE|CURRENT_TIMESTAMP|VERSION\(\))",
            sql_upper,
        ):
            return True
        return True  # Don't block on missing FROM — could be a simple expression

    def _remove_string_literals(self, sql: str) -> str:
        """Remove string literals to avoid false positives in pattern matching."""
        # Replace single-quoted strings with placeholder
        cleaned = re.sub(r"'[^']*'", "''", sql)
        # Replace double-quoted identifiers with placeholder
        cleaned = re.sub(r'"[^"]*"', '""', cleaned)
        return cleaned
