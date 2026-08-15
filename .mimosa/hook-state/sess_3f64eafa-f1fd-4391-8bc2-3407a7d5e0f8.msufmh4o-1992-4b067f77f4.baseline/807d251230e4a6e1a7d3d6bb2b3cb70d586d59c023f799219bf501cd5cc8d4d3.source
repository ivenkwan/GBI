# ADR 004: FlintChartBridge with Vega-Lite Fallback

**Status:** Accepted  
**Date:** 2026-07-04  
**Author:** Iven Kwan

## Context

Flint Chart (`flint-chart-mcp`) is v0.1.0 — very early stage, stdio-only transport, no HTTP/SSE, and subject to breaking changes. We need a chart rendering strategy that works today but can upgrade to Flint MCP when it stabilizes.

## Decision

**Implement a `FlintChartBridge` with a Vega-Lite/Altair fallback path.**

The bridge's architecture:

```
FlintChartBridge
  ├── Primary path: Flint MCP (via npx flint-chart-mcp stdio)
  │     ↓ compiles ChartAssemblyInput → Vega-Lite/ECharts/Chart.js → PNG/SVG
  │
  └── Fallback path: Altair (Python Vega-Lite wrapper)
        ↓ translates ChartAssemblyInput → Altair chart → SVG → PNG (via resvg)
```

The bridge auto-detects Flint availability and falls back silently. The `ChartAssemblyInput` schema is the unified API regardless of which path is active — callers never know whether Flint or Altair rendered the chart.

## Rationale

- **Ship without Flint dependency:** The system works with just Altair installed. Flint is a future upgrade.
- **Same schema, same output:** Both paths accept `ChartAssemblyInput` and produce PNG/SVG. Callers are unchanged.
- **Graceful degradation:** If Flint MCP isn't available (CI, dev machines without Node, production without npm), Altair handles everything.
- **Migration path:** When Flint reaches v1.0 with SSE transport, we flip the primary path and keep Altair as the fallback.

## Consequences

- **Positive:** Zero-risk Flint adoption. System runs today. Upgradable tomorrow.
- **Negative:** Altair has fewer chart types than Flint's full catalog. The fallback covers ~15 types vs. Flint's ~40. ECharts chart types (Sankey, radar, treemap) are Flint-only.
- **Mitigation:** The bridge returns warnings when a chart type falls outside Altair's supported set. The LLM is prompted to prefer types in the intersection.
