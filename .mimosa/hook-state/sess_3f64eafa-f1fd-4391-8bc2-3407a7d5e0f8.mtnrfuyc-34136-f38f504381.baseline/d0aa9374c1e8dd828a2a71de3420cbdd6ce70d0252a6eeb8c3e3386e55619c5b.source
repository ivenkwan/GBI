"""Catalog validation — the Cube-native semantic layer must stay coherent.

Parses every YAML under semantic/cube/model and asserts structural
invariants: unique names, real join targets, tenant dimension present, and
measures that the CubeClient /meta parser can consume. Pure offline — no
Cube or database required.
"""

from pathlib import Path

import pytest
import yaml

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "semantic" / "cube" / "model"


@pytest.fixture(scope="module")
def catalog() -> dict[str, dict]:
    files = sorted(SCHEMA_DIR.glob("*.yml"))
    assert files, f"no schema files found under {SCHEMA_DIR}"
    cubes: dict[str, dict] = {}
    for path in files:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        for cube in parsed.get("cubes", []):
            cubes[cube["name"]] = cube
    assert cubes, "catalog parsed to zero cubes"
    return cubes


def test_expected_cubes_present(catalog):
    assert set(catalog) == {
        "Sales",
        "Orders",
        "Customers",
        "Transactions",
        "WebUsers",
        "Activity",
        "Deals",
        "SalesReps",
        "Products",
        "Regions",
    }


def test_every_cube_has_measures_and_table(catalog):
    for name, cube in catalog.items():
        assert cube.get("sql_table"), f"{name} missing sql_table"
        assert cube.get("measures"), f"{name} has no measures"


def test_measure_names_unique_across_catalog(catalog):
    seen: set[str] = set()
    for cube in catalog.values():
        for measure in cube["measures"]:
            mname = measure["name"]
            assert mname not in seen, f"duplicate measure {mname}"
            seen.add(mname)


def test_every_cube_has_tenant_dimension(catalog):
    for name, cube in catalog.items():
        dims = {d["name"]: d for d in cube.get("dimensions", [])}
        assert "tenant_id" in dims, f"{name} missing tenant_id dimension"


def test_joins_reference_existing_cubes(catalog):
    for name, cube in catalog.items():
        for join in cube.get("joins", []):
            target = join["name"]
            assert target in catalog, f"{name} joins unknown cube {target}"


def test_join_pairs_are_symmetric(catalog):
    """Every join must be reciprocated (Cube requires both sides declared)."""
    for name, cube in catalog.items():
        for join in cube.get("joins", []):
            target = join["name"]
            back = {j["name"] for j in catalog[target].get("joins", [])}
            assert name in back, f"{name}->{target} join not reciprocated"


def test_time_dimensions_have_time_type(catalog):
    for name, cube in catalog.items():
        for dim in cube.get("dimensions", []):
            if dim.get("type") == "time":
                assert "date" in dim["name"] or "login" in dim["name"] or "hire" in dim["name"], (
                    f"{name}.{dim['name']} typed time but doesn't look temporal"
                )


def test_measures_declare_type_or_sql(catalog):
    """Cube needs either a simple type (count) or a sql expression."""
    for name, cube in catalog.items():
        for measure in cube["measures"]:
            assert measure.get("type") or measure.get("sql"), (
                f"{name}.{measure['name']} has neither type nor sql"
            )


def test_expected_core_metrics_exist(catalog):
    names = {f"{cube}.{m['name']}" for cube, defn in catalog.items() for m in defn["measures"]}
    for expected in (
        "Sales.revenue_total",
        "Sales.units_sold",
        "Orders.order_count",
        "Orders.order_value",
        "Customers.active_customers",
        "Transactions.transaction_volume",
        "WebUsers.active_users",
        "Activity.unique_active_users",
        "Deals.pipeline_value",
        "Deals.win_rate",
    ):
        assert expected in names, f"core metric {expected} missing"
