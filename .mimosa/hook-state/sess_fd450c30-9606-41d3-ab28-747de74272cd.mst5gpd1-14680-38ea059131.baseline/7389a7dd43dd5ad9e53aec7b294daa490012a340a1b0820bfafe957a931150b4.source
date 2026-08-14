# ADR 003: vis-flint Protocol Extension

**Status:** Accepted  
**Date:** 2026-07-04  
**Author:** Iven Kwan

## Context

DB-GPT's GPT-Vis protocol uses markdown code blocks (```vis-dashboard, ```vis_chart) to embed chart specifications in LLM responses. The frontend parses these blocks and renders AntV G2 charts. We need to extend this protocol for Flint Chart rendering.

## Decision

**Add a new `vis-flint` code block type that routes to Flint MCP for rendering.**

Extend the GPT-Vis protocol:
- ````vis-dashboard` → AntV G2 (existing, for interactive multi-chart dashboards)
- ````vis_chart` → AntV G2 (existing, for single interactive charts)
- ````vis-flint` → Flint MCP (new, for static PNG/SVG charts)

The vis-flint block contains a raw `ChartAssemblyInput` JSON spec:

````
```vis-flint
{
  "chartType": "Bar Chart",
  "encodings": {"x": {"field": "region"}, "y": {"field": "revenue"}},
  "data": {"values": [...]}
}
```
````

## Rationale

- **Backward compatible:** Existing vis-dashboard and vis_chart blocks continue to work with G2
- **Self-documenting:** The block type signals which renderer to use — no heuristic detection needed
- **AI-friendly:** The LLM emits the same `ChartAssemblyInput` schema it learned from Flint's agent skill
- **Frontend dispatch:** The markdown parser routes by block type — adding a new renderer is a registry entry

## Consequences

- **Positive:** Clean separation of static (Flint) and interactive (G2) chart paths. The LLM chooses the right format by emitting the right code block.
- **Negative:** Two rendering paths in the chat pipeline. Frontend needs to handle both SVG (Flint) and canvas (G2) embeds.
- **Implementation:** Backend `vis_flint_protocol.py` module parses vis-flint blocks, renders via FlintChartBridge, and replaces blocks with inline SVG or base64 PNG.
