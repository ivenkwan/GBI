"""RouterAgent — intent classification and agent dispatch.

Classifies the user's natural language query into one or more agent pipelines:
- chat_data: NL → SQL → execute → chart + narrative
- chat_knowledge: RAG over documents / knowledge base
- chat_visualize: Direct chart generation from inline data or file
- chat_explore: Schema exploration and data profiling
"""


from app.agents.base import AgentResult, BaseAgent
from app.agents.registry import register_agent


@register_agent("router")
class RouterAgent(BaseAgent):
    """Routes user queries to the appropriate agent pipeline."""

    name = "router"
    description = "Intent classifier and agent dispatch router"

    INTENTS = ["chat_data", "chat_visualize", "chat_knowledge", "chat_explore", "chat_report"]

    async def execute(
        self, query: str, conversation_history: list[dict] | None = None, **kwargs
    ) -> AgentResult:
        """Classify the query intent and return a dispatch plan."""
        import time

        start = time.time()

        intent = await self._classify_intent(query, tenant_id=kwargs.get("tenant_id"))
        plan = self._build_dispatch_plan(intent, query)

        return self._timed_result(
            AgentResult(
                agent_name=self.name,
                success=True,
                output={"intent": intent, "dispatch_plan": plan},
            ),
            start,
        )

    async def _classify_intent(self, query: str, tenant_id: str | None = None) -> str:
        """Classify query intent using a fast LLM call.

        Rides the shared LLMClient so tenant BYOK resolution applies — a
        tenant on a non-Anthropic provider must not ping the platform
        Anthropic key (403 with a placeholder key) on every query.
        """
        from app.core.llm_client import LLMCallOptions, get_llm_client

        prompt = f"""Classify this user query into exactly one intent category:
- chat_data: asking for data from a database (SQL query needed)
- chat_visualize: asking to create a chart or visualization
- chat_knowledge: asking about concepts, documentation, or knowledge
- chat_explore: asking to explore or understand a data schema
- chat_report: asking to generate a full report with charts and narrative

Query: {query}

Return ONLY a JSON object with the key "intent"."""

        result = await get_llm_client().invoke(
            prompt,
            options=LLMCallOptions(
                temperature=0,
                # Headroom for reasoning-style models whose hidden
                # reasoning_content eats into the budget before the JSON.
                max_tokens=2048,
                response_format="json",
            ),
            tenant_id=tenant_id,
        )
        intent = (result.parsed or {}).get("intent", "")
        if intent in self.INTENTS:
            return intent
        # Unparseable or out-of-vocabulary answer — safe default.
        return "chat_data"

    def _build_dispatch_plan(self, intent: str, query: str) -> list[dict]:
        """Build an ordered list of agent calls based on intent."""
        plans = {
            "chat_data": [
                {"agent": "nl2sql", "input": {"query": query}},
                {"agent": "validation", "input": {}},
                {"agent": "chart_gen", "input": {}},
                {"agent": "narrative", "input": {}},
            ],
            "chat_visualize": [
                {"agent": "chart_gen", "input": {"query": query}},
            ],
            "chat_report": [
                {"agent": "nl2sql", "input": {"query": query}},
                {"agent": "validation", "input": {}},
                {"agent": "chart_gen", "input": {}},
                {"agent": "narrative", "input": {}},
            ],
            "chat_knowledge": [
                {"agent": "narrative", "input": {"query": query, "mode": "rag"}},
            ],
            "chat_explore": [
                {"agent": "nl2sql", "input": {"query": query, "mode": "explore"}},
            ],
        }
        return plans.get(intent, [{"agent": "nl2sql", "input": {"query": query}}])
