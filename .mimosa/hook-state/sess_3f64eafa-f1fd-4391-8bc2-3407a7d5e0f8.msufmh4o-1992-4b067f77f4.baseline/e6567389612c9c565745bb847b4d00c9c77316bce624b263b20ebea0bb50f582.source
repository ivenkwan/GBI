# ADR 002: Multi-Agent Architecture with LangGraph

**Status:** Accepted  
**Date:** 2026-07-04  
**Author:** Iven Kwan

## Context

The GenBI pipeline (NL → SQL → Chart → Narrative) can be implemented as a single monolithic LLM call or as a chain of specialized agents. We need to decide the agent topology.

## Decision

**Multi-agent pipeline orchestrated by LangGraph, inspired by DB-GPT's AWEL patterns.**

```
User Query
  → RouterAgent (intent classification)
    → NL2SQLAgent (SQL generation with schema context)
      → ValidationAgent (SQL safety check + dry-run EXPLAIN)
        → Query Executor (read-only execution via SQLAlchemy)
          → ChartGenAgent (Flint ChartAssemblyInput spec + render)
            → NarrativeAgent (insight paragraph)
```

Each agent is a LangGraph node with a typed interface (`BaseAgent` → `AgentResult`). The `RouterAgent` classifies intent and selects which pipeline to run — not all queries need all agents.

## Rationale

**Why multi-agent over monolithic:**
- Specialized prompts produce better results (SQL agent focuses on SQL, chart agent on visual encoding, etc.)
- Each agent can use a different model (Opus-4 for SQL reasoning, Haiku-4 for chart specs)
- Independent testing and evaluation (golden NL2SQL test suite independent from chart quality)
- Audit trail at agent granularity (which agent hallucinated?)

**Why LangGraph over raw LangChain chains:**
- Conditional routing (skip chart if no data, add validation only for SQL paths)
- Checkpointing for multi-turn conversations
- Streaming per-agent progress to the frontend

## Consequences

- **Positive:** Modular, testable, observable. Model selection per agent. Independent iteration.
- **Negative:** More LLM calls per query (cost and latency). State management between agents. Need shared audit/observability layer.
- **Mitigation:** RouterAgent skips unnecessary agents. Fast model (Haiku-4) for non-SQL agents. Shared `AuditLog` model across all agents.
