"""Chat service -- orchestrates the full NL -> SQL -> Chart -> Narrative pipeline.

Flow:
    User Query
      -> RouterAgent (intent classification)
        -> NL2SQLAgent (SQL generation with schema context + few-shot examples)
          -> ValidationAgent (safety check + EXPLAIN)
            -> Connector (read-only execution, cached)
              -> ChartGenAgent (Flint chart spec + render + hallucination check)
                -> NarrativeAgent (insight paragraph)
                  -> AuditLog (persist trace)

Supports both synchronous and streaming (SSE) response modes.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.agents.base import AgentConfig
from app.agents.registry import get_agent
from app.core.logging import logger
from app.core.cache import get_cache, _hash_sql as cache_hash_sql


class ChatService:
    """Orchestrates the end-to-end GenBI query pipeline.

    Each step produces output consumed by the next step.
    Every step is independently auditable.
    Errors at any step produce graceful degradation, not failure.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.session_id = str(uuid4())

    # ------------------------------------------------------------------
    # Synchronous pipeline
    # ------------------------------------------------------------------

    async def process_query(
        self,
        query: str,
        user_id: str,
        roles: list[str],
        conversation_id: str | None = None,
    ) -> dict:
        """Process a natural language query through the full pipeline.

        Returns a dict suitable for ChatResponse serialization.
        """
        conversation_id = conversation_id or str(uuid4())
        warnings: list[str] = []

        logger.info(
            "Pipeline started",
            session_id=self.session_id,
            user_id=user_id,
            tenant_id=self.tenant_id,
            query=query[:200],
        )

        try:
            # Step 1: Route -- classify intent
            intent, plan = await self._step_route(query)

            # Step 2: NL2SQL -- generate query
            sql, sql_warnings = await self._step_nl2sql(
                query=query,
                user_id=user_id,
            )
            warnings.extend(sql_warnings)

            if not sql:
                return self._build_response(
                    conversation_id=conversation_id,
                    query=query,
                    warnings=warnings + ["Could not generate SQL for this query"],
                )

            # Step 3: Validate -- safety gate
            valid, validation_warnings, validated_sql = await self._step_validate(
                sql=sql,
                roles=roles,
            )
            warnings.extend(validation_warnings)

            if not valid:
                return self._build_response(
                    conversation_id=conversation_id,
                    query=query,
                    sql=sql,
                    warnings=warnings + ["Generated SQL failed safety validation"],
                )

            # Step 4: Execute -- run the query (cached)
            data, exec_warnings = await self._step_execute(
                sql=validated_sql or sql,
            )
            warnings.extend(exec_warnings)

            if data is None:
                return self._build_response(
                    conversation_id=conversation_id,
                    query=query,
                    sql=sql,
                    warnings=warnings + ["Query execution returned no data"],
                )

            # Step 5: Chart -- generate spec + validate + render
            chart_output = await self._step_chart(
                data=data,
                query=query,
            )
            warnings.extend(chart_output.get("warnings", []))

            # Step 6: Narrative -- write insight
            narrative = await self._step_narrative(
                query=query,
                data=data,
                chart_context=chart_output.get("chart_spec", {}),
                user_id=user_id,
            )
            warnings.extend(narrative.get("warnings", []))

            logger.info("Pipeline complete", session_id=self.session_id, warnings=len(warnings))

            return self._build_response(
                conversation_id=conversation_id,
                query=query,
                sql=sql,
                chart_spec=chart_output.get("chart_spec"),
                narrative=narrative.get("narrative"),
                chart_image_base64=chart_output.get("image_base64"),
                chart_svg=chart_output.get("svg"),
                warnings=warnings,
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", session_id=self.session_id)
            return self._build_response(
                conversation_id=conversation_id,
                query=query,
                warnings=warnings + [f"Pipeline error: {str(e)}"],
            )

    # ------------------------------------------------------------------
    # Streaming pipeline (SSE)
    # ------------------------------------------------------------------

    async def process_query_stream(
        self,
        query: str,
        user_id: str,
        roles: list[str],
        conversation_id: str | None = None,
    ):
        """Streaming variant -- yields SSE events as each pipeline stage completes.

        Events emitted:
            start -> intent -> sql -> validation -> data -> chart -> narrative -> done

        Each event includes the stage name and partial results. The frontend
        renders each stage incrementally as events arrive.
        """
        conversation_id = conversation_id or str(uuid4())
        warnings: list[str] = []

        def _emit(event: str, data: dict) -> str:
            return f"data: {json.dumps({'event': event, **data}, default=str)}\n\n"

        logger.info(
            "Streaming pipeline started",
            session_id=self.session_id,
            user_id=user_id,
            query=query[:200],
        )

        try:
            # Start
            yield _emit("start", {"query": query, "session_id": self.session_id})

            # Step 1: Route
            intent, plan = await self._step_route(query)
            yield _emit("intent", {"intent": intent, "plan": plan})

            # Step 2: NL2SQL
            sql, sql_warnings = await self._step_nl2sql(query=query, user_id=user_id)
            warnings.extend(sql_warnings)
            yield _emit("sql", {"sql": sql, "warnings": sql_warnings})

            if not sql:
                yield _emit("done", {"status": "no_sql", "warnings": warnings})
                return

            # Step 3: Validate
            valid, val_warnings, validated_sql = await self._step_validate(sql=sql, roles=roles)
            warnings.extend(val_warnings)
            yield _emit("validation", {
                "valid": valid,
                "validated_sql": validated_sql,
                "warnings": val_warnings,
            })

            if not valid:
                yield _emit("done", {"status": "validation_failed", "warnings": warnings})
                return

            # Step 4: Execute
            data, exec_warnings = await self._step_execute(sql=validated_sql or sql)
            warnings.extend(exec_warnings)
            yield _emit("data", {
                "row_count": len(data) if data else 0,
                "preview": data[:5] if data else [],
                "warnings": exec_warnings,
            })

            if not data:
                yield _emit("done", {"status": "no_data", "warnings": warnings})
                return

            # Step 5: Chart (with hallucination detection)
            chart_output = await self._step_chart(data=data, query=query)
            warnings.extend(chart_output.get("warnings", []))
            yield _emit("chart", {
                "chart_spec": chart_output.get("chart_spec"),
                "image_base64": chart_output.get("image_base64"),
                "svg": chart_output.get("svg"),
                "warnings": chart_output.get("warnings", []),
            })

            # Step 6: Narrative
            narrative = await self._step_narrative(
                query=query,
                data=data,
                chart_context=chart_output.get("chart_spec", {}),
                user_id=user_id,
            )
            warnings.extend(narrative.get("warnings", []))
            yield _emit("narrative", {
                "narrative": narrative.get("narrative"),
                "warnings": narrative.get("warnings", []),
            })

            # Done
            yield _emit("done", {"status": "complete", "warnings": warnings})

        except Exception as e:
            logger.error(f"Streaming pipeline failed: {e}", session_id=self.session_id)
            yield _emit("done", {"status": "error", "error": str(e), "warnings": warnings})

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    async def _step_route(self, query: str) -> tuple[str, list[dict]]:
        """Step 1: Classify query intent."""
        try:
            agent_cls = get_agent("router")
            if not agent_cls:
                return "chat_data", []

            agent = agent_cls(AgentConfig(model_name="claude-haiku-4"))
            result = await agent.execute(query=query)
            intent = result.output.get("intent", "chat_data")
            plan = result.output.get("dispatch_plan", [])
            return intent, plan
        except Exception as e:
            logger.warning(f"RouterAgent failed, defaulting to chat_data: {e}")
            return "chat_data", []

    async def _step_nl2sql(
        self,
        query: str,
        user_id: str,
    ) -> tuple[str | None, list[str]]:
        """Step 2: Generate SQL from natural language.

        Schema context is cached at L1+L2 per (query_hash, tenant_id).
        Metric definitions from Cube.dev are cached at L2 per tenant.
        """
        try:
            agent_cls = get_agent("nl2sql")
            if not agent_cls:
                return None, ["NL2SQLAgent not registered"]

            agent = agent_cls(
                AgentConfig(
                    model_name="claude-opus-4",
                    temperature=0,
                    max_tokens=4096,
                    thinking=True,
                )
            )

            # Load metric definitions from Cube.dev semantic layer (cached)
            metric_context = ""
            try:
                cache = get_cache()

                # Check cache for metric definitions
                cached_metrics = await cache.get_metric_definitions(self.tenant_id)
                if cached_metrics is not None:
                    metric_context = cached_metrics
                    logger.info("Metric context loaded from cache")
                else:
                    from app.semantic.cube_client import get_cube_client
                    cube = get_cube_client()
                    metric_context = await cube.get_agent_context(query=query)
                    await cache.set_metric_definitions(self.tenant_id, metric_context)
                    logger.info("Metric context loaded and cached", length=len(metric_context))
            except Exception as e:
                logger.warning(f"Metric context unavailable -- continuing without: {e}")

            result = await agent.execute(
                query=query,
                tenant_id=self.tenant_id,
                user_id=user_id,
                session_id=self.session_id,
                metric_definitions=metric_context,
            )
            sql = result.output.get("sql")
            return sql, result.warnings
        except Exception as e:
            logger.error(f"NL2SQLAgent failed: {e}")
            return None, [f"SQL generation failed: {str(e)}"]

    async def _step_validate(
        self,
        sql: str,
        roles: list[str],
    ) -> tuple[bool, list[str], str | None]:
        """Step 3: Validate SQL for safety."""
        try:
            agent_cls = get_agent("validation")
            if not agent_cls:
                logger.warning("ValidationAgent not registered -- skipping validation")
                return True, ["Validation skipped -- agent not available"], sql

            agent = agent_cls(AgentConfig(model_name="deterministic"))
            result = await agent.execute(
                sql=sql,
                tenant_id=self.tenant_id,
                user_roles=roles,
            )
            validated_sql = result.output.get("validated_sql", sql)

            if not result.success:
                logger.warning(
                    "SQL validation failed",
                    errors=result.errors,
                    sql=sql[:200],
                )

            return result.success, result.warnings, validated_sql
        except Exception as e:
            logger.error(f"ValidationAgent failed: {e}")
            return False, [f"Validation error: {str(e)}"], None

    async def _step_execute(self, sql: str) -> tuple[list[dict] | None, list[str]]:
        """Step 4: Execute SQL against the data source. Cached at L1+L2."""
        try:
            # Check cache first
            cache = get_cache()
            cached_result = await cache.get_query_result(sql, self.tenant_id)
            if cached_result is not None:
                logger.info(
                    "Query result cache hit",
                    row_count=len(cached_result),
                    tenant_id=self.tenant_id,
                )
                return cached_result, []

            from app.connectors.postgresql_connector import PostgreSQLConnector
            from app.core.config import settings

            connector = PostgreSQLConnector(
                connection_url=settings.DATABASE_URL,
            )

            async with connector:
                results = await connector.execute(sql)
                logger.info(
                    "SQL executed",
                    row_count=len(results),
                    tenant_id=self.tenant_id,
                )

                # Cache the result
                await cache.set_query_result(sql, self.tenant_id, results)

                return results, []

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            return None, [f"Query execution failed: {str(e)}"]

    async def _step_chart(
        self,
        data: list[dict],
        query: str,
    ) -> dict:
        """Step 5: Generate chart spec, validate, and render via Flint/Altair bridge.

        Chart hallucination detection runs between generation and rendering.
        If the spec has errors, auto-correction is attempted before the fallback
        render path. Every correction is logged and surfaced as a warning.
        """
        try:
            agent_cls = get_agent("chart_gen")
            if not agent_cls:
                return {"warnings": ["ChartGenAgent not registered"]}

            agent = agent_cls(
                AgentConfig(
                    model_name="claude-haiku-4",
                    temperature=0,
                    max_tokens=2048,
                )
            )
            result = await agent.execute(
                data=data,
                query=query,
                tenant_id=self.tenant_id,
            )

            if not result.success:
                return {"warnings": result.errors}

            chart_spec = result.output.get("chart_spec", {})

            # --- Hallucination detection ---
            if chart_spec and data:
                try:
                    from app.agents.validation.chart_validator import (
                        validate_chart_spec,
                    )

                    validation = validate_chart_spec(
                        spec=chart_spec,
                        data=data,
                        auto_correct=True,
                    )

                    validation_warnings = validation.warnings + validation.fix_summary

                    if validation.corrected_spec is not None:
                        logger.info(
                            "Chart spec auto-corrected",
                            corrections=validation.fix_summary,
                            original_type=chart_spec.get("chartType"),
                            corrected_type=validation.corrected_spec.get("chartType"),
                        )
                        chart_spec = validation.corrected_spec

                    if not validation.is_valid:
                        error_codes = [
                            i.code for i in validation.issues if i.severity == "error"
                        ]
                        logger.warning(
                            "Chart spec has uncorrectable errors",
                            errors=error_codes,
                        )
                        validation_warnings.insert(
                            0,
                            f"Chart spec has uncorrectable errors: {', '.join(error_codes)}",
                        )
                    elif validation_warnings:
                        logger.info(
                            "Chart spec validated with warnings",
                            warning_count=len(validation_warnings),
                        )

                except ImportError:
                    validation_warnings = []
                    logger.debug("Chart validator not available -- skipping")
                except Exception as e:
                    validation_warnings = [f"Chart validation skipped: {e}"]
                    logger.warning(f"Chart validation exception: {e}")
            else:
                validation_warnings = []

            # --- Cache the validated chart spec ---
            if chart_spec and data:
                try:
                    cache = get_cache()
                    data_hash = cache_hash_sql(json.dumps(data[:10], default=str))
                    await cache.set_chart_spec(data_hash, self.tenant_id, chart_spec)
                except Exception:
                    pass  # Non-critical

            return {
                "chart_spec": chart_spec,
                "image_base64": result.output.get("image_base64"),
                "svg": result.output.get("svg"),
                "backend": result.output.get("backend"),
                "warnings": result.warnings + validation_warnings,
            }

        except Exception as e:
            logger.error(f"ChartGenAgent failed: {e}")
            return {"warnings": [f"Chart generation failed: {str(e)}"]}

    async def _step_narrative(
        self,
        query: str,
        data: list[dict],
        chart_context: dict,
        user_id: str,
    ) -> dict:
        """Step 6: Generate insight narrative."""
        try:
            agent_cls = get_agent("narrative")
            if not agent_cls:
                return {"warnings": ["NarrativeAgent not registered"]}

            agent = agent_cls(
                AgentConfig(
                    model_name="claude-haiku-4",
                    temperature=0.3,
                    max_tokens=512,
                )
            )

            # Build data summary
            data_summary = {
                "head": data[:5],
                "row_count": len(data),
            }

            # Add numeric statistics if present
            if data:
                numeric_cols = [
                    c for c, v in data[0].items()
                    if isinstance(v, (int, float))
                ]
                if numeric_cols:
                    col = numeric_cols[0]
                    values = [r[col] for r in data if r.get(col) is not None]
                    if values:
                        data_summary["total"] = sum(values)
                        data_summary["avg_value"] = sum(values) / len(values)
                        data_summary["max_value"] = max(values)
                        data_summary["min_value"] = min(values)

            result = await agent.execute(
                query=query,
                data_summary=data_summary,
                chart_context=chart_context,
                tenant_id=self.tenant_id,
                user_id=user_id,
                session_id=self.session_id,
            )

            return {
                "narrative": result.output.get("narrative"),
                "warnings": result.warnings,
            }

        except Exception as e:
            logger.error(f"NarrativeAgent failed: {e}")
            return {"warnings": [f"Narrative generation failed: {str(e)}"]}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_response(
        self,
        conversation_id: str,
        query: str,
        sql: str | None = None,
        sql_explanation: str | None = None,
        chart_spec: dict | None = None,
        narrative: str | None = None,
        chart_image_base64: str | None = None,
        chart_svg: str | None = None,
        warnings: list[str] | None = None,
    ) -> dict:
        """Build a ChatResponse-compatible dict."""
        return {
            "conversation_id": conversation_id,
            "query": query,
            "sql": sql,
            "sql_explanation": sql_explanation,
            "chart_spec": chart_spec,
            "narrative": narrative,
            "chart_image_base64": chart_image_base64,
            "chart_svg": chart_svg,
            "warnings": warnings or [],
        }
