# Agent System

> See also: [ADR 002: Multi-Agent Architecture](adr/002-agent-architecture.md) | [Architecture Overview](architecture-overview.md)

## Overview

The GenBI agent system is a **six-agent pipeline** orchestrated by **LangGraph**, inspired by DB-GPT's AWEL (Agentic Workflow Expression Language) patterns. Each agent is a LangGraph node with a typed interface (`BaseAgent` → `AgentResult`). The `RouterAgent` classifies intent and selects which pipeline to run — not all queries need all agents.

**Two-tier LLM usage:**
- **Reasoning tasks** (NL2SQL) → `claude-opus-4` with extended thinking
- **Fast tasks** (classification, chart spec, narrative) → `claude-haiku-4`
- **Safety tasks** (SQL validation, chart validation) → deterministic, zero LLM calls

---

## Base Framework

### AgentConfig

```python
@dataclass
class AgentConfig:
    model_name: str
    temperature: float = 0.0
    max_tokens: int = 4096
    thinking: bool = False  # Enables Claude extended thinking
```

### AgentResult

Every agent returns this envelope. The `success` flag is the primary pass/fail indicator.

```python
@dataclass
class AgentResult:
    agent_name: str
    success: bool
    output: dict
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0
    model_version: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
```

### BaseAgent (Abstract Class)

```python
class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = "Base agent class"

    def __init__(self, config: AgentConfig):
        self.config = config
        self._run_id = str(uuid4())

    @abstractmethod
    async def execute(self, **kwargs) -> AgentResult:
        """Execute the agent's core logic. Must be overridden by subclasses."""

    def _timed_result(self, result: AgentResult, start_time: float) -> AgentResult:
        result.latency_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
        return result
```

**Contract:** All agents accept typed `**kwargs` in `execute()`, return `AgentResult` (never raw exceptions), and call `_timed_result()` to attach latency.

### Registry

```python
_registry: dict[str, type[BaseAgent]] = {}

def register_agent(name: str):
    """Decorator to register an agent class in the global registry."""
    def decorator(cls: type[BaseAgent]) -> type[BaseAgent]:
        cls.name = name
        _registry[name] = cls
        return cls
    return decorator

def get_agent(name: str) -> type[BaseAgent] | None: ...
def list_agents() -> list[str]: ...
```

Agents self-register via the `@register_agent("name")` decorator on their class. Import triggers registration — no central file needed.

---

## Agent Roster

### 1. RouterAgent

| Attribute | Value |
|---|---|
| **Registered as** | `"router"` |
| **Purpose** | Classify user query intent and return a dispatch plan |
| **LLM** | `settings.LLM_FAST_MODEL` (Haiku-4), temp=0, max_tokens=256 |
| **Key method** | `async def execute(self, query: str, conversation_history: list[dict] | None = None, **kwargs) -> AgentResult` |

**Intent classification:**
| Intent | Pipeline |
|---|---|
| `chat_data` | nl2sql → validation → chart_gen → narrative |
| `chat_visualize` | chart_gen |
| `chat_report` | nl2sql → validation → chart_gen → narrative |
| `chat_knowledge` | narrative (mode: rag) |
| `chat_explore` | nl2sql (mode: explore) |
| *fallback* | nl2sql |

The router returns the plan as output — it does NOT invoke downstream agents. The orchestrator (`ChatService`) reads `output["dispatch_plan"]` and executes steps sequentially.

---

### 2. NL2SQLAgent

| Attribute | Value |
|---|---|
| **Registered as** | `"nl2sql"` |
| **Purpose** | Generate read-only SQL from natural language |
| **LLM** | `settings.LLM_REASONING_MODEL` (Opus-4), thinking=True, temp=0, max_tokens=4096 |
| **Prompt** | `.claude/prompts/nl2sql-system.md` (loaded via `load_prompt`) |
| **Output format** | JSON (structured output extraction) |

**Input kwargs:**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | Yes | User's natural language question |
| `schema_context` | `list[dict] \| None` | No | Top-k relevant tables from pgvector |
| `few_shot_examples` | `list[dict] \| None` | No | Similar validated NL/SQL pairs |
| `metric_definitions` | `list[dict] \| str \| None` | No | Business metrics from Cube.dev |
| `tenant_id` | `str` | No | Default `"default"` |
| `user_id` | `str` | No | For audit |
| `session_id` | `str` | No | For audit |

**Output:** `AgentResult.output` contains `{"sql": "...", "explanation": "...", "tables_used": [...], "assumptions": [...], "run_id": "..."}`

**Safety:** Runs `_check_destructive_patterns(sql)` — regex-based detection of 11 destructive SQL patterns (DROP, DELETE, TRUNCATE, ALTER, UPDATE, INSERT, CREATE USER, GRANT, REVOKE, COPY FROM). This is defense-in-depth; `ValidationAgent` runs a more comprehensive check downstream.

---

### 3. ValidationAgent

| Attribute | Value |
|---|---|
| **Registered as** | `"validation"` |
| **Purpose** | Deterministic SQL safety gate — zero LLM calls |
| **Protection** | Marked protected in CLAUDE.md — any relaxation requires security review |

**Input kwargs:** `sql: str | None`, `tenant_id: str = "default"`, `user_roles: list[str] | None`, `connector=None` (optional read connector with `explain(sql)` — ChatService passes one so the EXPLAIN dry-run runs under the RLS tenant GUC)

**Seven safety checks (sequential):**
1. **Multi-statement injection** — detects `;`-delimited statements outside string literals
2. **Destructive patterns** — 17 hard-blocked (DROP, DELETE, TRUNCATE, ALTER, UPDATE, INSERT, CREATE, GRANT, REVOKE, COPY FROM, ...) + 4 warned (UPDATE/INSERT/CREATE TABLE/CREATE INDEX shapes)
3. **Read-only enforcement** — only `SELECT`, `WITH`, `EXPLAIN`, `SHOW`, `DESCRIBE` pass
4. **Timeout policy** — metadata only (`statement_timeout: "30s"` in output); enforced by the connector via `SET LOCAL` at execution time. The validator never mutates the SQL (a regression test pins this)
5. **Basic sanity** — requires FROM/WHERE (currently always returns True)
6. **EXPLAIN dry-run** — runs `EXPLAIN (FORMAT JSON)` via the connector when the SQL is otherwise valid; fail-open (EXPLAIN problems never block)
7. **Row count estimate** — >1M estimated rows sets `requires_confirmation: true` + an advisory warning; the pipeline then stops before execution until the client re-sends with `confirm_large_query: true` (Phase 13)

**Output:** `AgentResult.success` is the pass/fail verdict. `output` carries `validated_sql` (clean, unmutated), `statement_timeout`, `explain_plan`, `row_estimate`, `requires_confirmation`. The SSE `validation` event surfaces `valid`, `validated_sql`, `requires_confirmation`, `row_estimate`, `warnings`.

---

### 4. ChartGenAgent

| Attribute | Value |
|---|---|
| **Registered as** | `"chart_gen"` |
| **Purpose** | Generate chart specifications from data and render via Flint MCP |
| **LLM** | `settings.LLM_FAST_MODEL` (Haiku-4), thinking=False, temp=0, max_tokens=2048 |

**Input kwargs:** `data: list[dict] | None`, `query: str | None`, `intent: str | None`, `preferred_chart_type: str | None`, `tenant_id: str = "default"`

**Pipeline:**
1. `_infer_semantic_types(data)` — samples first 20 rows, classifies columns as Category/Quantity/Temporal
2. `_suggest_chart_type(data, semantic_types)` — rule-based: Line if temporal+quantity, Bar if single category, Scatter if 2+ quantities, Pie if few rows
3. `_suggest_encodings(data, semantic_types, chart_type)` — assigns x (temporal > category), y (first quantity), color
4. LLM invocation — produces `ChartAssemblyInput` spec (JSON output, extraction fallbacks)
5. `FlintChartBridge.render(spec)` — renders via Flint MCP or Vega-Lite/Altair fallback

**Dependencies:** `FlintChartBridge` (bridge to Flint/Vega-Lite), `ChartValidator` (post-render hallucination check)

#### Chart Subsystem

The chart subsystem has three files:

| File | Purpose |
|---|---|
| `chart/flint_bridge.py` | `FlintChartBridge` — renders specs via Flint MCP or Altair/Vega-Lite fallback. 31 supported chart types. Auto-detects Flint availability. |
| `chart/vis_flint_protocol.py` | Extends DB-GPT's GPT-Vis with `vis-flint` markdown code blocks. Parses, renders, replaces with inline SVG/base64 PNG. |
| `chart/flint_operator.py` | AWEL-compatible operator for DB-GPT Flow Canvas. Wraps ChartGenAgent + FlintChartBridge. |

See: [ADR 001](adr/001-dual-chart-stack.md) | [ADR 003](adr/003-vis-flint-protocol.md) | [ADR 004](adr/004-flint-bridge-fallback.md)

---

### 5. NarrativeAgent

| Attribute | Value |
|---|---|
| **Registered as** | `"narrative"` |
| **Purpose** | Data storytelling — 3-5 sentence insight paragraphs for business stakeholders |
| **LLM** | `settings.LLM_FAST_MODEL` (Haiku-4), thinking=False, temp=0.3, max_tokens=512 |
| **Prompt** | `.claude/prompts/narrative-system.md` |

**Input kwargs:** `query: str`, `data_summary: dict | None`, `chart_context: dict | None`, `sql: str`, `tenant_id: str`, `user_id: str`, `session_id: str`

**Quality checks** (`_quality_checks(narrative) -> list[str]`):
1. **Length:** 2-8 sentences ideal; warns if shorter or longer
2. **Vague language:** flags "many", "large", "significant", "substantial", "most", "some", "few", "various", "generally", "typically"

---

### 6. Chart Validator (Deterministic)

| Attribute | Value |
|---|---|
| **Purpose** | Catch and correct LLM hallucinations in chart specifications — zero LLM calls |
| **Philosophy** | Correction over rejection — prefers fuzzy-match fix over failing the request |

**Validation categories:**

| Function | What it checks |
|---|---|
| `validate_spec_structure` | Missing required keys, empty data, no encodings |
| `validate_data_size` | >10K rows (warn), 0 rows (error) |
| `validate_field_existence` | Encoding fields match actual data columns; fuzzy-match correction |
| `validate_chart_type_compatibility` | Type compatibility per chart-type requirements |
| `validate_data_ranges` | Negative business metrics, axis bounds vs data range |
| `validate_null_handling` | >20% null values in an encoding field |

**Correction fallback chain:** Pie → Bar, Scatter → Line → Bar, Line → Bar, Heatmap → Table, universal → Bar.

---

## Pipeline Data Flow

```
User Query
  │
  ├─ RouterAgent._classify_intent(query)    [Haiku, no thinking]
  │    └─ Returns: "chat_data", dispatch=["nl2sql","validation","chart_gen","narrative"]
  │
  ├─ CubeClient.get_agent_context(query)    [Semantic layer — cached metric definitions]
  │
  ├─ NL2SQLAgent.execute(query, ...)        [Opus, thinking, structured JSON]
  │    └─ Output: {sql, explanation, tables_used, assumptions}
  │
  ├─ ValidationAgent.execute(sql)           [Deterministic — 7 checks]
  │    └─ Output: {validated_sql, is_valid}
  │
  ├─ PostgreSQLConnector.execute(sql)       [Read-only, 30s timeout]
  │    └─ Output: rows (list[dict])
  │
  ├─ ChartGenAgent.execute(data=rows)       [Haiku, no thinking]
  │    ├─ _generate_chart_spec() → spec
  │    ├─ FlintChartBridge.render(spec) → SVG/PNG
  │    └─ ChartValidator.validate_chart_spec(spec, data) → corrected spec
  │    └─ Output: {chart_spec, image_base64/svg}
  │
  └─ NarrativeAgent.execute(...)            [Haiku, temp=0.3, max_tokens=512]
       └─ Output: {narrative}
```

## LLM Model Usage Summary

| Agent | Model | Thinking | Temperature | Max Tokens | Prompt |
|---|---|---|---|---|---|
| RouterAgent | Haiku-4 | No | 0.0 | 256 | Inline |
| NL2SQLAgent | Opus-4 | **Yes** | 0.0 | 4096 | `.claude/prompts/nl2sql-system.md` |
| ValidationAgent | *None* | N/A | N/A | N/A | N/A |
| ChartGenAgent | Haiku-4 | No | 0.0 | 2048 | Inline |
| NarrativeAgent | Haiku-4 | No | 0.3 | 512 | `.claude/prompts/narrative-system.md` |
| ChartValidator | *None* | N/A | N/A | N/A | N/A |

## Design Principles

1. **Two-tier LLM usage** — reasoning tasks use Opus with thinking; fast tasks use Haiku
2. **Deterministic safety gates** — SQL and chart validation run zero LLM calls
3. **Defense in depth** — NL2SQLAgent has its own destructive-pattern check; ValidationAgent runs independent checks downstream
4. **Registry pattern** — agents self-register via decorator; no central registration file
5. **Prompt-as-code** — system prompts live in `.claude/prompts/*.md`, versioned in git
6. **Structured output** — NL2SQL and Chart Gen both request JSON output with extraction fallbacks
7. **Correction over rejection** — Chart Validator prefers fixing hallucinations over failing
