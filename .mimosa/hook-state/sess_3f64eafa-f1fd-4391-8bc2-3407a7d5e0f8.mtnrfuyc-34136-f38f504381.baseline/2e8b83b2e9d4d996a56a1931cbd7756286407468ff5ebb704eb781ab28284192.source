"""FlintChartOperator — AWEL-compatible operator for the Flow Canvas.

This operator wraps FlintChartBridge into a reusable DAG node that can be
dropped into DB-GPT-style visual workflows. It:

1. Accepts a DataFrame from a preceding SQL execution operator
2. Introspects column types and suggests chart type + encodings
3. Generates a ChartAssemblyInput spec via LLM (if needed)
4. Renders the chart via FlintChartBridge
5. Returns a ChartResult (PNG/SVG) to downstream operators

The operator is designed to follow DB-GPT's AWEL MapOperator pattern
so it can be registered on the Flow Canvas alongside existing operators.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChartOperatorInput:
    """Input to the FlintChartOperator — typically comes from SQL execution."""

    data: list[dict] = field(default_factory=list)
    chart_type_hint: str | None = None
    title: str | None = None
    description: str | None = None


@dataclass
class ChartOperatorOutput:
    """Output from the FlintChartOperator — consumed by report assembly or chat response."""

    success: bool
    spec: dict = field(default_factory=dict)
    image_base64: str | None = None
    svg: str | None = None
    format: str = "png"
    backend: str = "vegalite"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def flint_chart_operator(
    input_data: ChartOperatorInput,
    tenant_id: str = "default",
    backend: str = "vegalite",
    output_format: str = "png",
) -> ChartOperatorOutput:
    """Execute the Flint chart operator.

    This function is the AWEL operator entry point. In a full DB-GPT deployment,
    it would be wrapped as a MapOperator subclass with ViewMetadata for the canvas.

    Usage in AWEL:
        with DAG("sales_report") as dag:
            sql_node = SQLOperator(...)
            chart_node = MapOperator.from_fn(flint_chart_operator)
            sql_node >> chart_node
    """
    from app.agents.chart.flint_bridge import FlintChartBridge
    from app.agents.chart_gen_agent import ChartGenAgent
    from app.agents.base import AgentConfig

    # Generate spec
    agent = ChartGenAgent(
        config=AgentConfig(
            model_name="claude-haiku-4",
            temperature=0,
        )
    )

    result = await agent._generate_chart_spec(
        data=input_data.data,
        preferred_chart_type=input_data.chart_type_hint,
    )

    # Render
    bridge = FlintChartBridge(tenant_id=tenant_id)
    render_result = await bridge.render(
        spec=result,
        backend=backend,
        output_format=output_format,
    )

    return ChartOperatorOutput(
        success=render_result.get("success", False),
        spec=result,
        image_base64=render_result.get("image_base64"),
        svg=render_result.get("svg"),
        format=output_format,
        backend=backend,
        warnings=render_result.get("warnings", []),
        errors=render_result.get("errors", []),
    )
