# LLM Prompt Engineering Conventions

## Model selection

- Use `settings.LLM_REASONING_MODEL` (claude-opus-4) for SQL generation, complex reasoning
- Use `settings.LLM_FAST_MODEL` (claude-haiku-4) for intent classification, chart specs, narratives
- NEVER hardcode model names in business logic

## Prompt template management

- Prompt templates are versioned files in `.claude/prompts/`
- Load templates with `load_prompt("prompt_name")` — never inline long prompts
- Templates use `{variable}` substitution with Pydantic validation

## Schema context compression

- Embed only relevant table/column metadata into LLM context
- Use pgvector cosine similarity to retrieve top-k relevant tables
- Never send the full database schema to the LLM
- Include column descriptions from dbt schema.yml in the context

## Chain of thought

- Reasoning models (opus-4) always use `thinking` blocks for SQL generation
- Fast models (haiku-4) use direct generation

## Error handling

- LLM calls always go through `llm_client.py` which handles timeout + retry, token budgets, and latency tracking

## Few-shot examples

- Stored in `backend/app/agents/examples/` as JSON files
- Load dynamically based on query similarity via pgvector
- Never hardcode examples in source code
