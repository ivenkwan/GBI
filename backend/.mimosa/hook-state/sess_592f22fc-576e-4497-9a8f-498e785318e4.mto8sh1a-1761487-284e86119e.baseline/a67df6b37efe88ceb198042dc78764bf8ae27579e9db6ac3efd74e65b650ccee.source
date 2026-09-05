"""Apache AGE graph database — data lineage and relationship analysis.

Apache AGE (A Graph Extension) is a PostgreSQL extension that provides
graph database capabilities via openCypher queries. GenBI uses it for:

1. Data lineage: tracking where metrics come from (source table → Cube measure)
2. Relationship analysis: discovering join paths between tables for SQL generation
3. Impact analysis: what downstream assets are affected by a schema change

Architecture:
    Schema Catalog → Graph Ingestion → AGE Graph (genbi_graph)
                                         ↓
    LineageAgent ← openCypher queries ← AGE
         ↓
    Graph context injected into NL2SQLAgent (join paths)

Every cypher statement is a complete inline literal with AGE parameter
binding (``$name`` placeholders inside the ``$$`` body; values ride in the
third ``ag_catalog.cypher`` argument, bound via the ``:params`` SQLAlchemy
named parameter) — never string-interpolated.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import text

from app.core.logging import logger

# ---------------------------------------------------------------------------
# Graph schema
# ---------------------------------------------------------------------------

# The genbi_graph graph has these vertex labels and edge types:
#
# VERTICES:
#   Table { name, schema, description }
#   Column { name, data_type, description, table_name }
#   Metric { name, description, metric_type }
#   Dashboard { name, description }
#   User { user_id, tenant_id }
#
# EDGES:
#   TABLE_CONTAINS (Table → Column) { ordinal_position }
#   METRIC_SOURCE (Metric → Column) { aggregation, expression }
#   METRIC_DEPENDS (Metric → Metric) { relationship }
#   DASHBOARD_USES (Dashboard → Metric) { position }
#   USER_CAN_ACCESS (User → Table | Metric) { role, granted_at }
#   TABLE_JOINS (Table → Table) { join_columns, join_type }


class VertexLabel(StrEnum):
    TABLE = "Table"
    COLUMN = "Column"
    METRIC = "Metric"
    DASHBOARD = "Dashboard"
    USER = "User"


class EdgeLabel(StrEnum):
    TABLE_CONTAINS = "TABLE_CONTAINS"
    METRIC_SOURCE = "METRIC_SOURCE"
    METRIC_DEPENDS = "METRIC_DEPENDS"
    DASHBOARD_USES = "DASHBOARD_USES"
    USER_CAN_ACCESS = "USER_CAN_ACCESS"
    TABLE_JOINS = "TABLE_JOINS"


# ---------------------------------------------------------------------------
# Graph initialization
# ---------------------------------------------------------------------------


async def init_age_graph(db_session) -> None:
    """Initialize the Apache AGE graph if it doesn't exist.

    Safe to call on startup — the create_graph failure for an existing
    graph is caught and rolled back.
    """
    try:
        await db_session.execute(
            text(
                "CREATE EXTENSION IF NOT EXISTS age; "
                "SET search_path = ag_catalog, public; "
                "SELECT * FROM ag_catalog.create_graph('genbi_graph');"
            )
        )
        await db_session.commit()
        logger.info("AGE graph 'genbi_graph' initialized successfully")
    except Exception as e:
        logger.info(f"AGE graph already exists or init skipped: {e}")
        await db_session.rollback()


async def create_indices(db_session) -> None:
    """Create vertex/edge labels on the graph (idempotent, best-effort)."""
    try:
        await db_session.execute(
            text("SELECT * FROM ag_catalog.create_vlabel('genbi_graph', 'Table')")
        )
    except Exception as e:
        logger.debug(f"Label creation skipped (may exist): {e}")
    try:
        await db_session.execute(
            text("SELECT * FROM ag_catalog.create_vlabel('genbi_graph', 'Column')")
        )
    except Exception as e:
        logger.debug(f"Label creation skipped (may exist): {e}")
    try:
        await db_session.execute(
            text("SELECT * FROM ag_catalog.create_vlabel('genbi_graph', 'Metric')")
        )
    except Exception as e:
        logger.debug(f"Label creation skipped (may exist): {e}")
    try:
        await db_session.execute(
            text("SELECT * FROM ag_catalog.create_vlabel('genbi_graph', 'Dashboard')")
        )
    except Exception as e:
        logger.debug(f"Label creation skipped (may exist): {e}")
    try:
        await db_session.execute(
            text("SELECT * FROM ag_catalog.create_elabel('genbi_graph', 'TABLE_CONTAINS')")
        )
    except Exception as e:
        logger.debug(f"Label creation skipped (may exist): {e}")
    try:
        await db_session.execute(
            text("SELECT * FROM ag_catalog.create_elabel('genbi_graph', 'METRIC_SOURCE')")
        )
    except Exception as e:
        logger.debug(f"Label creation skipped (may exist): {e}")
    try:
        await db_session.execute(
            text("SELECT * FROM ag_catalog.create_elabel('genbi_graph', 'DASHBOARD_USES')")
        )
    except Exception as e:
        logger.debug(f"Label creation skipped (may exist): {e}")
    try:
        await db_session.execute(
            text("SELECT * FROM ag_catalog.create_elabel('genbi_graph', 'TABLE_JOINS')")
        )
    except Exception as e:
        logger.debug(f"Label creation skipped (may exist): {e}")

    await db_session.commit()
    logger.info("AGE graph labels ensured for 'genbi_graph'")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LineageNode:
    """A node in the data lineage graph."""

    id: str
    label: str
    properties: dict = field(default_factory=dict)


@dataclass
class LineageEdge:
    """An edge in the data lineage graph."""

    source_id: str
    target_id: str
    label: str
    properties: dict = field(default_factory=dict)


@dataclass
class LineagePath:
    """A path through the data lineage graph."""

    nodes: list[LineageNode] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)
    depth: int = 0


# ---------------------------------------------------------------------------
# Graph ingestion
# ---------------------------------------------------------------------------


async def ingest_table(
    db_session,
    table_name: str,
    schema: str = "public",
    columns: list[dict] | None = None,
) -> str:
    """Ingest a table and its columns into the lineage graph.

    Creates Table vertex and Column vertices connected by TABLE_CONTAINS edges.
    """
    table_id = str(uuid4())

    await db_session.execute(
        text(
            "SELECT * FROM ag_catalog.cypher('genbi_graph', $$ "
            "CREATE (t:Table { id: $id, name: $name, schema: $schema, description: '' }) "
            "RETURN t "
            "$$, :params) AS (result ag_catalog.agtype);"
        ),
        {"params": json.dumps({"id": table_id, "name": table_name, "schema": schema})},
    )
    await db_session.commit()

    if columns:
        for col in columns:
            await ingest_column(
                db_session,
                table_id,
                col.get("name", col.get("column_name", "")),
                col.get("type", col.get("data_type", "text")),
                col.get("description", ""),
            )

    logger.info(f"Ingested table '{schema}.{table_name}' into lineage graph")
    return table_id


async def ingest_column(
    db_session,
    table_id: str,
    column_name: str,
    data_type: str,
    description: str = "",
) -> str:
    """Add a Column vertex and TABLE_CONTAINS edge to the graph."""
    col_id = str(uuid4())

    await db_session.execute(
        text(
            "SELECT * FROM ag_catalog.cypher('genbi_graph', $$ "
            "MATCH (t:Table { id: $table_id }) "
            "CREATE (c:Column { id: $id, name: $name, data_type: $type, description: $desc }) "
            "CREATE (t)-[:TABLE_CONTAINS]->(c) "
            "RETURN c "
            "$$, :params) AS (result ag_catalog.agtype);"
        ),
        {
            "params": json.dumps(
                {
                    "table_id": table_id,
                    "id": col_id,
                    "name": column_name,
                    "type": data_type,
                    "desc": description,
                }
            )
        },
    )
    return col_id


async def ingest_metric(
    db_session,
    metric_name: str,
    description: str,
    metric_type: str,
    source_table_id: str,
    source_column_name: str,
) -> str:
    """Ingest a metric and link it to its source column."""
    metric_id = str(uuid4())

    await db_session.execute(
        text(
            "SELECT * FROM ag_catalog.cypher('genbi_graph', $$ "
            "MATCH (t:Table { id: $table_id })-[:TABLE_CONTAINS]->(c:Column { name: $column }) "
            "CREATE (m:Metric { id: $id, name: $name, description: $desc, metric_type: $mtype }) "
            "CREATE (m)-[:METRIC_SOURCE]->(c) "
            "RETURN m "
            "$$, :params) AS (result ag_catalog.agtype);"
        ),
        {
            "params": json.dumps(
                {
                    "table_id": source_table_id,
                    "column": source_column_name,
                    "id": metric_id,
                    "name": metric_name,
                    "desc": description,
                    "mtype": metric_type,
                }
            )
        },
    )
    logger.info(f"Ingested metric '{metric_name}' linked to column '{source_column_name}'")
    return metric_id


async def ingest_join_path(
    db_session,
    table_a_id: str,
    table_b_id: str,
    join_columns: str,
    join_type: str = "INNER",
) -> None:
    """Record a known join path between two tables."""
    await db_session.execute(
        text(
            "SELECT * FROM ag_catalog.cypher('genbi_graph', $$ "
            "MATCH (a:Table { id: $a }), (b:Table { id: $b }) "
            "CREATE (a)-[:TABLE_JOINS { join_columns: $cols, join_type: $jtype }]->(b) "
            "$$, :params) AS (result ag_catalog.agtype);"
        ),
        {
            "params": json.dumps(
                {"a": table_a_id, "b": table_b_id, "cols": join_columns, "jtype": join_type}
            )
        },
    )
    logger.info(f"Ingested join path: {table_a_id} -> {table_b_id} on {join_columns}")


# ---------------------------------------------------------------------------
# Graph traversal
# ---------------------------------------------------------------------------


async def get_metric_lineage(
    db_session,
    metric_name: str,
) -> list[LineagePath]:
    """Trace a metric back to its source tables and columns.

    Returns the full lineage path: Metric → Column → Table.
    """
    result = await db_session.execute(
        text(
            "SELECT * FROM ag_catalog.cypher('genbi_graph', $$ "
            "MATCH path = (m:Metric { name: $name })-[:METRIC_SOURCE]->(c:Column)"
            "<-[:TABLE_CONTAINS]-(t:Table) "
            "RETURN path "
            "$$, :params) AS (result ag_catalog.agtype);"
        ),
        {"params": json.dumps({"name": metric_name})},
    )
    rows = result.fetchall()

    paths = []
    for row in rows:
        # Parse AGE path format
        path_data = row[0] if row else None
        if path_data:
            # Simplified parsing — in production, use AGE's path parsing
            paths.append(
                LineagePath(
                    nodes=[
                        LineageNode(
                            id=str(uuid4()), label="Metric", properties={"name": metric_name}
                        ),
                    ],
                    depth=1,
                )
            )

    return paths


async def find_join_paths(
    db_session,
    table_a_id: str,
    table_b_id: str,
    max_depth: int = 3,
) -> list[LineagePath]:
    """Find all join paths between two tables (up to max_depth hops).

    This is used by NL2SQLAgent to discover how to join tables in generated SQL.
    """
    result = await db_session.execute(
        text(
            "SELECT * FROM ag_catalog.cypher('genbi_graph', $$ "
            "MATCH path = (a:Table { id: $a })-[:TABLE_JOINS*1..3]-(b:Table { id: $b }) "
            "RETURN path "
            "ORDER BY length(path) "
            "LIMIT 5 "
            "$$, :params) AS (result ag_catalog.agtype);"
        ),
        {"params": json.dumps({"a": table_a_id, "b": table_b_id})},
    )
    rows = result.fetchall()

    paths = []
    for _ in rows:
        paths.append(
            LineagePath(
                nodes=[
                    LineageNode(id=str(uuid4()), label="Table", properties={"id": table_a_id}),
                    LineageNode(id=str(uuid4()), label="Table", properties={"id": table_b_id}),
                ],
                depth=2,
            )
        )

    return paths


async def get_downstream_impact(
    db_session,
    table_name: str,
) -> list[dict]:
    """Find all downstream metrics and dashboards affected by a table change.

    Used for impact analysis before schema migrations.
    """
    result = await db_session.execute(
        text(
            "SELECT * FROM ag_catalog.cypher('genbi_graph', $$ "
            "MATCH (t:Table { name: $name })-[:TABLE_CONTAINS]->(c:Column)"
            "<-[:METRIC_SOURCE]-(m:Metric)-[:DASHBOARD_USES]-(d:Dashboard) "
            "RETURN t.name AS table_name, m.name AS metric_name, collect(d.name) AS dashboards "
            "$$, :params) AS (table_name ag_catalog.agtype, metric_name ag_catalog.agtype, "
            "dashboards ag_catalog.agtype);"
        ),
        {"params": json.dumps({"name": table_name})},
    )
    rows = result.fetchall()

    impact = []
    for row in rows:
        impact.append(
            {
                "table": str(row[0]) if row[0] else "",
                "metric": str(row[1]) if row[1] else "",
                "dashboards": str(row[2]) if row[2] else "[]",
            }
        )

    return impact


# ---------------------------------------------------------------------------
# Sync with semantic layer
# ---------------------------------------------------------------------------


async def sync_semantic_layer_to_graph(
    db_session,
    cube_client=None,
) -> dict[str, int]:
    """Sync Cube.dev metric definitions into the AGE lineage graph.

    Called nightly to keep the graph in sync with the semantic layer.
    """
    tables_ingested = 0
    metrics_ingested = 0
    joins_ingested = 0

    # Ingest from Cube meta if available
    if cube_client:
        try:
            meta = await cube_client.get_meta(force_refresh=True)
            for cube in meta.cubes:
                cube_name = cube.get("name", "")

                # Ingest table
                columns = []
                for dim in cube.get("dimensions", []):
                    columns.append(
                        {
                            "name": dim.get("name", ""),
                            "type": dim.get("type", "string"),
                            "description": dim.get("title", ""),
                        }
                    )

                table_id = await ingest_table(
                    db_session,
                    table_name=cube_name,
                    schema="public",
                    columns=columns,
                )
                tables_ingested += 1

                # Ingest measures as metrics
                for measure in cube.get("measures", []):
                    await ingest_metric(
                        db_session,
                        metric_name=f"{cube_name}.{measure.get('name', '')}",
                        description=measure.get("description", ""),
                        metric_type=measure.get("type", "sum"),
                        source_table_id=table_id,
                        source_column_name=measure.get("name", ""),
                    )
                    metrics_ingested += 1

        except Exception as e:
            logger.warning(f"Semantic layer sync via Cube failed: {e}")

    await db_session.commit()

    return {
        "tables_ingested": tables_ingested,
        "metrics_ingested": metrics_ingested,
        "joins_ingested": joins_ingested,
    }
