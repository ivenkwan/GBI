# ADR 001: Dual Chart Stack — Flint MCP + AntV G2

**Status:** Accepted  
**Date:** 2026-07-04  
**Author:** Iven Kwan

## Context

GenBI needs to render charts from natural language queries. We evaluated two approaches:

1. **AntV G2 only** (DB-GPT's default): Interactive, web-native charts using G2's Grammar of Graphics. Used by DB-GPT's GPT-Vis protocol.
2. **Flint MCP only** (Microsoft's new chart framework): Unified `ChartAssemblyInput` spec compiled to Vega-Lite/ECharts/Chart.js. MCP-native, local rendering, PNG+SVG output.

## Decision

**We will use a dual-stack approach:**

- **Flint MCP** for static, export-quality charts (PNG/SVG for reports, emails, documents, dashboards)
- **AntV G2** (via GPT-Vis protocol) for interactive dashboard widgets (hover, zoom, brush, drill-down)

These are complementary, not competing. The agent pipeline selects the appropriate renderer based on context:

| Scenario | Renderer |
|---|---|
| Chat response with chart | Flint (SVG embedded inline) |
| Report generation | Flint (PNG at 2x scale) |
| Interactive dashboard tile | G2 (interactive canvas) |
| Email attachment | Flint (PNG) |
| Data exploration with brushing | G2 (interactive) |

## Rationale

**Why not Flint-only:** Flint is v0.1.0, stdio-only transport, no interactive features. It can't handle live dashboard widgets with hover/zoom/brush. Maturity risk for critical-path production use.

**Why not G2-only:** G2 produces only canvas/web output — no clean PNG/SVG export for documents and emails. The LLM has to navigate G2's complex configuration directly. Flint's unified schema is simpler for AI agents to author.

**Why both:** Each solves the other's weakness. Flint's unified schema is the AI-friendly authoring format. G2 is the interactive rendering engine. The `vis-flint` protocol extension routes static charts to Flint and interactive ones to G2.

## Consequences

- **Positive:** Best-in-class output for each use case. AI agent gets simple schema (Flint), users get interactive exploration (G2).
- **Negative:** Two chart stacks to maintain, deploy, and debug. Vendor risk on Flint (Microsoft, v0.1.0). Need `flint-chart-mcp` Node.js dependency alongside Python backend.
- **Mitigation:** FlintChartBridge has a Vega-Lite/Altair fallback path that doesn't require Flint MCP at all — the system runs without Flint if needed. Flint can be added later when it stabilizes.
