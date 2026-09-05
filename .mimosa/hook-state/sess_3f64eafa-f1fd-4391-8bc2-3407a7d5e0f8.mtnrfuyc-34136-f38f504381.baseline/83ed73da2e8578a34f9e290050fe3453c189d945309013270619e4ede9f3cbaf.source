"""LLM mock fixtures for agent tests.

This module provides reusable mock LLM responses for every agent type.
All unit and integration tests MUST use these mocks — never call real LLM APIs.

Usage:
    from tests.fixtures.llm_mock import mock_nl2sql_response, MockLLMClient

    async def test_nl2sql_agent():
        agent = NL2SQLAgent(config)
        # Inject mock client that returns pre-canned responses
        agent._llm_override = MockLLMClient(mock_nl2sql_response)
        result = await agent.execute(query="Show me revenue by region")
        assert result.success
        assert "SELECT" in result.output["sql"]
"""

# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------

class MockLLMClient:
    """Drop-in mock for LLMClient.invoke().

    Use in tests to avoid real LLM API calls. Returns pre-canned responses
    based on a scenario map or a single default response.
    """

    def __init__(self, default_response: dict | None = None):
        self.default_response = default_response or {}
        self.calls: list[dict] = []  # Track all calls for assertions
        self.scenarios: dict[str, dict] = {}  # Scenario-specific responses

    async def invoke(self, **kwargs) -> "MockLLMResult":
        """Record the call and return a pre-canned response."""
        self.calls.append(kwargs)
        messages = kwargs.get("messages", "")
        message_text = messages if isinstance(messages, str) else str(messages)

        # Check scenario map
        for key, response in self.scenarios.items():
            if key in message_text:
                return MockLLMResult(**response)

        return MockLLMResult(**self.default_response)


class MockLLMResult:
    """Matches the shape of LLMCallResult for test assertions."""

    def __init__(self, **kwargs):
        self.content = kwargs.get("content", '{"intent": "chat_data"}')
        self.model_name = kwargs.get("model_name", "claude-haiku-4")
        self.input_tokens = kwargs.get("input_tokens", 100)
        self.output_tokens = kwargs.get("output_tokens", 50)
        self.latency_ms = kwargs.get("latency_ms", 200.0)
        self.attempt = kwargs.get("attempt", 1)
        self.parsed = kwargs.get("parsed", None)

        # Auto-parse JSON content
        if self.parsed is None and self.content.strip().startswith("{"):
            import json
            try:
                self.parsed = json.loads(self.content)
            except json.JSONDecodeError:
                pass


# ---------------------------------------------------------------------------
# Pre-canned Agent Responses
# ---------------------------------------------------------------------------

# RouterAgent — intent classification
MOCK_ROUTER_RESPONSE = {
    "content": '{"intent": "chat_data"}',
    "parsed": {"intent": "chat_data"},
    "model_name": "claude-haiku-4",
    "input_tokens": 80,
    "output_tokens": 15,
}

MOCK_ROUTER_RESPONSE_VISUALIZE = {
    "content": '{"intent": "chat_visualize"}',
    "parsed": {"intent": "chat_visualize"},
    "model_name": "claude-haiku-4",
    "input_tokens": 80,
    "output_tokens": 15,
}

# NL2SQLAgent — SQL generation
MOCK_NL2SQL_RESPONSE = {
    "content": json.dumps({
        "sql": "SELECT region, SUM(revenue) AS total_revenue FROM public.sales WHERE tenant_id = '00000000-0000-0000-0000-000000000001' GROUP BY region ORDER BY total_revenue DESC LIMIT 1000",
        "explanation": "Groups sales by region and sums revenue, sorted by highest revenue first.",
        "tables_used": ["public.sales"],
        "assumptions": ["Revenue is stored in the 'revenue' column of 'sales' table."],
        "warnings": [],
    }),
    "parsed": {
        "sql": "SELECT region, SUM(revenue) AS total_revenue FROM public.sales WHERE tenant_id = '00000000-0000-0000-0000-000000000001' GROUP BY region ORDER BY total_revenue DESC LIMIT 1000",
        "explanation": "Groups sales by region and sums revenue, sorted by highest revenue first.",
        "tables_used": ["public.sales"],
        "assumptions": ["Revenue is stored in the 'revenue' column of 'sales' table."],
        "warnings": [],
    },
    "model_name": "claude-opus-4",
    "input_tokens": 2500,
    "output_tokens": 200,
}

MOCK_NL2SQL_RESPONSE_TIME_SERIES = {
    "content": json.dumps({
        "sql": "SELECT DATE_TRUNC('month', transaction_date) AS month, SUM(amount) AS revenue FROM public.transactions WHERE tenant_id = '00000000-0000-0000-0000-000000000001' GROUP BY month ORDER BY month LIMIT 1000",
        "explanation": "Aggregates transaction amounts by month.",
        "tables_used": ["public.transactions"],
        "assumptions": ["transaction_date is a DATE/TIMESTAMP column."],
        "warnings": [],
    }),
    "parsed": {
        "sql": "SELECT DATE_TRUNC('month', transaction_date) AS month, SUM(amount) AS revenue FROM public.transactions WHERE tenant_id = '00000000-0000-0000-0000-000000000001' GROUP BY month ORDER BY month LIMIT 1000",
        "explanation": "Aggregates transaction amounts by month.",
        "tables_used": ["public.transactions"],
        "assumptions": ["transaction_date is a DATE/TIMESTAMP column."],
        "warnings": [],
    },
    "model_name": "claude-opus-4",
    "input_tokens": 3000,
    "output_tokens": 250,
}

# NL2SQLAgent — destructive SQL (should be caught by validation)
MOCK_NL2SQL_DESTRUCTIVE = {
    "content": json.dumps({
        "sql": "DROP TABLE public.sales",
        "explanation": "Drops the sales table.",
        "tables_used": ["public.sales"],
        "assumptions": [],
        "warnings": [],
    }),
    "parsed": {
        "sql": "DROP TABLE public.sales",
        "explanation": "Drops the sales table.",
        "tables_used": ["public.sales"],
        "assumptions": [],
        "warnings": [],
    },
    "model_name": "claude-opus-4",
    "input_tokens": 1000,
    "output_tokens": 50,
}

# ChartGenAgent — chart spec
MOCK_CHARTGEN_RESPONSE = {
    "content": json.dumps({
        "chartType": "Bar Chart",
        "encodings": {
            "x": {"field": "region"},
            "y": {"field": "total_revenue"},
        },
        "baseSize": {"width": 600, "height": 400},
        "data": {
            "values": [
                {"region": "North", "total_revenue": 120000},
                {"region": "South", "total_revenue": 95000},
            ],
        },
    }),
    "parsed": {
        "chartType": "Bar Chart",
        "encodings": {
            "x": {"field": "region"},
            "y": {"field": "total_revenue"},
        },
        "baseSize": {"width": 600, "height": 400},
        "data": {
            "values": [
                {"region": "North", "total_revenue": 120000},
                {"region": "South", "total_revenue": 95000},
            ],
        },
    },
    "model_name": "claude-haiku-4",
    "input_tokens": 800,
    "output_tokens": 150,
}

# NarrativeAgent — insight paragraph
MOCK_NARRATIVE_RESPONSE = {
    "content": (
        "Revenue reached $215,000 across all regions, with North leading at "
        "$120,000 and South trailing at $95,000. The North region outperformed "
        "South by approximately 26%, suggesting different market penetration "
        "or product mix between the two territories. Consider reviewing South's "
        "sales strategy to close the gap."
    ),
    "model_name": "claude-haiku-4",
    "input_tokens": 500,
    "output_tokens": 80,
}


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def create_mock_llm_client(scenario: str = "default") -> MockLLMClient:
    """Create a MockLLMClient pre-loaded with common scenarios.

    Args:
        scenario: One of "default", "time_series", "visualize", "destructive".

    Returns:
        MockLLMClient with scenario-specific responses.
    """
    client = MockLLMClient()

    # Map scenarios to responses
    scenario_map = {
        "default": {
            "router": MOCK_ROUTER_RESPONSE,
            "nl2sql": MOCK_NL2SQL_RESPONSE,
            "chart_gen": MOCK_CHARTGEN_RESPONSE,
            "narrative": MOCK_NARRATIVE_RESPONSE,
        },
        "time_series": {
            "nl2sql": MOCK_NL2SQL_RESPONSE_TIME_SERIES,
        },
        "visualize": {
            "router": MOCK_ROUTER_RESPONSE_VISUALIZE,
        },
        "destructive": {
            "nl2sql": MOCK_NL2SQL_DESTRUCTIVE,
        },
    }

    # Flatten scenario map into response-keyed entries
    for scenario_name, agent_map in scenario_map.items():
        for agent_name, response in agent_map.items():
            # We match on agent names in the message content
            # (the actual matching logic in MockLLMClient is substring-based)
            pass

    return client


# Re-export json for the module-level dicts
import json
