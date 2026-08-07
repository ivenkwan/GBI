"""Tests for the ValidationAgent — SQL safety gate.

The ValidationAgent is deterministic (no LLM) so these are pure unit tests.
"""

import pytest

from app.agents.base import AgentConfig
from app.agents.validation.validation_agent import ValidationAgent


@pytest.fixture
def agent():
    return ValidationAgent(
        AgentConfig(model_name="deterministic")
    )


# ---------------------------------------------------------------------------
# Valid queries — should pass
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_valid_simple_select(agent):
    """Basic SELECT should pass validation."""
    result = await agent.execute(
        sql="SELECT region, SUM(revenue) FROM sales GROUP BY region"
    )
    assert result.success
    assert len(result.errors) == 0


@pytest.mark.unit
async def test_valid_with_cte(agent):
    """CTE (WITH clause) should pass validation."""
    result = await agent.execute(
        sql="WITH regional_sales AS (SELECT region, SUM(revenue) as total FROM sales GROUP BY region) SELECT * FROM regional_sales WHERE total > 10000"
    )
    assert result.success


@pytest.mark.unit
async def test_valid_explain(agent):
    """EXPLAIN should pass validation."""
    result = await agent.execute(
        sql="EXPLAIN SELECT * FROM sales"
    )
    assert result.success


@pytest.mark.unit
async def test_reports_timeout_policy_without_mutating_sql(agent):
    """Validation reports the timeout policy and returns CLEAN SQL.

    The validator must not inject `SET LOCAL statement_timeout` into the SQL
    string itself — that enforcement belongs to the connector at execution
    time. Wrapping the SQL here caused the connector's read-only/SELECT gate
    to reject every validated query (the wrapped string no longer started with
    SELECT). This test guards against that regression.
    """
    result = await agent.execute(
        sql="SELECT * FROM sales"
    )
    validated_sql = result.output.get("validated_sql", "")
    # SQL is returned clean and unmutated
    assert validated_sql == "SELECT * FROM sales"
    assert "SET LOCAL" not in validated_sql
    assert ";" not in validated_sql
    # Timeout is surfaced as policy metadata instead
    assert result.output.get("statement_timeout") == agent.STATEMENT_TIMEOUT


# ---------------------------------------------------------------------------
# Destructive queries — should be rejected
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_rejects_drop_table(agent):
    """DROP TABLE must be rejected."""
    result = await agent.execute(sql="DROP TABLE sales")
    assert not result.success
    assert any("DROP TABLE" in e for e in result.errors)


@pytest.mark.unit
async def test_rejects_delete(agent):
    """DELETE FROM must be rejected."""
    result = await agent.execute(sql="DELETE FROM sales WHERE id = 1")
    assert not result.success


@pytest.mark.unit
async def test_rejects_truncate(agent):
    """TRUNCATE must be rejected."""
    result = await agent.execute(sql="TRUNCATE TABLE sales")
    assert not result.success


@pytest.mark.unit
async def test_rejects_insert(agent):
    """INSERT must be rejected."""
    result = await agent.execute(
        sql="INSERT INTO sales (region, revenue) VALUES ('North', 100)"
    )
    assert not result.success


@pytest.mark.unit
async def test_rejects_update(agent):
    """UPDATE must be rejected (with warning)."""
    result = await agent.execute(
        sql="UPDATE sales SET revenue = 200 WHERE region = 'North'"
    )
    assert not result.success or len(result.warnings) > 0
    # UPDATE triggers warning, but the statement is also not SELECT
    assert not result.success


# ---------------------------------------------------------------------------
# Multi-statement injection
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_rejects_multi_statement(agent):
    """Multiple statements separated by ; should be rejected."""
    result = await agent.execute(
        sql="SELECT * FROM sales; DROP TABLE users"
    )
    assert not result.success
    assert any("Multi-statement" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_rejects_empty_sql(agent):
    """Empty SQL should be rejected."""
    result = await agent.execute(sql="")
    assert not result.success


@pytest.mark.unit
async def test_rejects_none_sql(agent):
    """None SQL should be rejected."""
    result = await agent.execute(sql=None)
    assert not result.success


@pytest.mark.unit
async def test_simple_expression_without_from(agent):
    """SELECT without FROM (e.g. SELECT now()) should pass."""
    result = await agent.execute(sql="SELECT NOW()")
    assert result.success


@pytest.mark.unit
async def test_row_estimate_warning(agent):
    """Queries over MAX_ROW_ESTIMATE should produce warnings."""
    # We can't actually run EXPLAIN without a connector, so this just
    # verifies the output structure
    result = await agent.execute(
        sql="SELECT * FROM very_large_table"
    )
    assert "requires_confirmation" in result.output
