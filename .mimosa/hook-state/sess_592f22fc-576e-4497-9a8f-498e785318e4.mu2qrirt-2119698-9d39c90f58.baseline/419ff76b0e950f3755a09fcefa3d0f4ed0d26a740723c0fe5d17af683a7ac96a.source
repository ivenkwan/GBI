"""Chart endpoints — render charts via Flint MCP and manage chart history."""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models.chart import ChartRenderRequest, ChartRenderResponse

router = APIRouter()


@router.post("/render", response_model=ChartRenderResponse)
async def render_chart(
    request: ChartRenderRequest,
    user: dict = Depends(get_current_user),
):
    """Render a chart from a ChartAssemblyInput spec using Flint MCP.
    Supports Vega-Lite, ECharts, and Chart.js backends. Returns PNG or SVG."""
    from app.agents.chart.flint_bridge import FlintChartBridge

    bridge = FlintChartBridge(tenant_id=user["tenant_id"])
    result = await bridge.render(
        spec=request.spec,
        backend=request.backend or "vegalite",
        output_format=request.format or "png",
    )
    return ChartRenderResponse(**result)
