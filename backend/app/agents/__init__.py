"""Agent package — agents self-register via ``@register_agent`` when their
module is imported, so the server's import chain must load them somewhere.
Tests import the classes directly; the API server only ever imported
``app.agents.base``/``registry``, leaving the registry empty at runtime and
every pipeline step falling through with "<Agent> not registered". Importing
the implementations here means any entry point that touches this package
(``from app.agents.base import ...`` in chat_service, scripts, uvicorn boot)
gets a fully populated registry.
"""

from app.agents.chart_gen_agent import ChartGenAgent
from app.agents.narrative.narrative_agent import NarrativeAgent
from app.agents.nl2sql.nl2sql_agent import NL2SQLAgent
from app.agents.router_agent import RouterAgent
from app.agents.validation.validation_agent import ValidationAgent

__all__ = [
    "RouterAgent",
    "NL2SQLAgent",
    "ChartGenAgent",
    "NarrativeAgent",
    "ValidationAgent",
]
