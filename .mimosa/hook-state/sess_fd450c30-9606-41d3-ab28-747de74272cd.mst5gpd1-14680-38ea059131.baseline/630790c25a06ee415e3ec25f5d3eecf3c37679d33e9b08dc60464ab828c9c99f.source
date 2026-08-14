"""NarrativeAgent — data storytelling and insight generation.

Writes concise, actionable insight paragraphs from data and chart context.
Designed for business stakeholders: lead with the finding, use specific numbers,
and include a suggested action.

Model: claude-haiku-4 (fast, direct generation)
Prompt: .claude/prompts/narrative-system.md
"""

import re
import time
from uuid import uuid4

from app.agents.base import AgentConfig, AgentResult, BaseAgent
from app.agents.registry import register_agent
from app.core.llm_client import LLMCallOptions, get_llm_client, load_prompt
from app.core.logging import logger


@register_agent("narrative")
class NarrativeAgent(BaseAgent):
    """Generates data insight narratives from query results and charts.

    Input: User's original question + data summary + chart context
    Output: 3-5 sentence insight paragraph in flowing prose
    """

    name = "narrative"
    description = "Data storyteller — generates concise insight paragraphs"

    async def execute(
        self,
        query: str = "",
        data_summary: dict | None = None,
        chart_context: dict | None = None,
        sql: str = "",
        tenant_id: str = "default",
        user_id: str = "",
        session_id: str = "",
        **kwargs,
    ) -> AgentResult:
        """Generate a narrative insight from data and chart.

        Args:
            query: The user's original natural language question.
            data_summary: Summary statistics from the query result (rows, totals, trends).
            chart_context: Chart type, encodings, and key visual patterns.
            sql: The generated SQL (for context, not included in narrative).
            tenant_id: Multi-tenant identifier.
            user_id: User identifier for audit logging.
            session_id: Session identifier for audit logging.
        """
        start = time.time()
        run_id = str(uuid4())
        session_id = session_id or run_id

        logger.info(
            "NarrativeAgent starting",
            run_id=run_id,
            has_data=bool(data_summary),
            has_chart=bool(chart_context),
        )

        if not data_summary and not chart_context:
            return self._timed_result(
                AgentResult(
                    agent_name=self.name,
                    success=False,
                    output={},
                    errors=["No data summary or chart context provided to NarrativeAgent"],
                ),
                start,
            )

        # Build the prompt
        system_prompt = load_prompt("narrative-system")
        user_message = self._build_user_message(
            query=query,
            data_summary=data_summary,
            chart_context=chart_context,
        )

        try:
            client = get_llm_client()
            result = await client.invoke(
                messages=user_message,
                system=system_prompt,
                use_reasoning=False,  # Haiku — fast, direct generation
                options=LLMCallOptions(
                    temperature=0.3,  # Slight warmth for natural prose
                    max_tokens=512,  # 3-5 sentences
                    timeout_seconds=30,
                    max_retries=2,
                ),
                user_id=user_id,
                tenant_id=tenant_id,
                session_id=session_id,
            )

            narrative = result.content.strip()

            # Quality checks
            checks = self._quality_checks(narrative)

            return self._timed_result(
                AgentResult(
                    agent_name=self.name,
                    success=bool(narrative),
                    output={
                        "narrative": narrative,
                        "query": query,
                        "run_id": run_id,
                    },
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    model_version=result.model_name,
                    warnings=checks,
                ),
                start,
            )

        except Exception as e:
            logger.error(f"NarrativeAgent failed: {e}")
            return self._timed_result(
                AgentResult(
                    agent_name=self.name,
                    success=False,
                    output={"run_id": run_id},
                    errors=[str(e)],
                ),
                start,
            )

    def _build_user_message(
        self,
        query: str,
        data_summary: dict | None,
        chart_context: dict | None,
    ) -> str:
        """Build the user message with all available context."""
        import json

        parts = []

        # User's question
        if query:
            parts.append(f"**User asked**: {query}")

        # Data summary
        if data_summary:
            parts.append("\n## Data Summary\n")
            if data_summary.get("head"):
                parts.append("### Sample Rows")
                parts.append("```json")
                parts.append(json.dumps(data_summary["head"][:5], default=str))
                parts.append("```")

            stats = []
            if data_summary.get("row_count"):
                stats.append(f"- Total rows: {data_summary['row_count']}")
            if data_summary.get("total_revenue"):
                stats.append(f"- Total revenue: ${data_summary['total_revenue']:,.2f}")
            if data_summary.get("avg_value"):
                stats.append(f"- Average: {data_summary['avg_value']:,.2f}")
            if data_summary.get("trend"):
                stats.append(f"- Trend: {data_summary['trend']}")
            if data_summary.get("notable_outlier"):
                stats.append(f"- Notable outlier: {data_summary['notable_outlier']}")

            if stats:
                parts.append("\n### Key Statistics\n" + "\n".join(stats))

        # Chart context
        if chart_context:
            parts.append("\n## Chart Context\n")
            parts.append(f"- Chart type: {chart_context.get('chartType', 'unknown')}")
            if chart_context.get("encodings"):
                enc = chart_context["encodings"]
                parts.append(f"- X-axis: {enc.get('x', {}).get('field', 'N/A')}")
                parts.append(f"- Y-axis: {enc.get('y', {}).get('field', 'N/A')}")
                if enc.get("color"):
                    parts.append(f"- Color/Series: {enc['color'].get('field', 'N/A')}")

        return "\n".join(parts)

    def _quality_checks(self, narrative: str) -> list[str]:
        """Run quality checks on the generated narrative.

        Returns advisory warnings — the narrative is still returned even with warnings.
        """
        warnings = []

        # Check length (3-5 sentences is ideal)
        sentences = [s.strip() for s in narrative.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        if len(sentences) < 2:
            warnings.append("Narrative is short (< 2 sentences) — may lack actionable insight")
        if len(sentences) > 8:
            warnings.append("Narrative is long (> 8 sentences) — consider tightening to key findings")

        # Check for vague language
        vague_terms = ["many", "large", "small", "significant", "a lot", "various", "several"]
        found_vague = [t for t in vague_terms if re.search(rf"\b{t}\b", narrative.lower())]
        if found_vague:
            warnings.append(f"Vague terms found: {', '.join(found_vague)} — use specific numbers instead")

        return warnings
