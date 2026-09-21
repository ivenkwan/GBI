"""Deterministic-dataset contract tests (offline)."""

import json

from demo import dataset

from . import _SCRIPTS  # noqa: F401 — ensures scripts/ is on sys.path


def _canon(obj) -> str:
    return json.dumps(obj, default=str, sort_keys=True)


class TestRoster:
    def test_default_roster_is_the_documented_pair(self):
        roster = dataset.build_roster(2)
        assert [(t["name"], t["slug"]) for t in roster] == [
            ("Acme Analytics", "demo-acme"),
            ("Globex Retail", "demo-globex"),
        ]

    def test_extra_tenants_are_generated_with_unique_slugs(self):
        roster = dataset.build_roster(4)
        slugs = [t["slug"] for t in roster]
        assert len(set(slugs)) == 4
        assert slugs[2] == "demo-tenant-3"

    def test_users_per_tenant_with_roles_and_unique_emails(self):
        for entry in dataset.build_roster(2):
            assert [u["display_role"] for u in entry["users"]] == ["admin", "analyst", "viewer"]
            assert entry["users"][0]["roles"] == ["admin", "user"]
            assert entry["users"][1]["roles"] == ["user"]
            assert entry["users"][2]["roles"] == ["viewer"]
            emails = [u["email"] for u in entry["users"]]
            assert emails == [f"{r}@{entry['slug']}.test" for r in ("admin", "analyst", "viewer")]

    def test_ids_are_stable_across_calls(self):
        assert dataset.build_roster(2) == dataset.build_roster(2)

    def test_tenant_settings_marker(self):
        settings = dataset.tenant_settings(42)
        assert settings == {"demo": True, "seed": 42, "demo_version": dataset.DEMO_VERSION}


class TestDeterminism:
    def test_same_seed_produces_identical_analytics(self):
        entry = dataset.build_roster(1)[0]
        a1, c1 = dataset.build_dataset(entry, seed=42)
        a2, c2 = dataset.build_dataset(entry, seed=42)
        assert _canon(a1) == _canon(a2)
        assert _canon(c1) == _canon(c2)

    def test_different_seed_produces_different_data(self):
        entry = dataset.build_roster(1)[0]
        a1, _ = dataset.build_dataset(entry, seed=42)
        a2, _ = dataset.build_dataset(entry, seed=43)
        assert _canon(a1) != _canon(a2)

    def test_different_tenants_differ_but_keep_shape(self):
        roster = dataset.build_roster(2)
        a1, _ = dataset.build_dataset(roster[0], seed=42)
        a2, _ = dataset.build_dataset(roster[1], seed=42)
        assert set(a1) == set(a2) == set(dataset.TABLE_COLUMNS)
        assert _canon(a1) != _canon(a2)

    def test_row_counts_match_the_seed_script_defaults(self):
        entry = dataset.build_roster(1)[0]
        analytics, _ = dataset.build_dataset(entry, seed=42)
        assert len(analytics["sales"]) == 500
        assert len(analytics["customers"]) == 100
        assert len(analytics["orders"]) == 1000
        assert len(analytics["transactions"]) == 2000
        assert len(analytics["web_users"]) == 200
        assert len(analytics["deals"]) == 300
        assert len(analytics["activity"]) == 5000
        assert len(analytics["products"]) == len(dataset.PRODUCT_NAMES)
        assert len(analytics["regions"]) == len(dataset.REGIONS)
        assert len(analytics["sales_representatives"]) == len(dataset.SALES_REPS)

    def test_date_windows_are_the_fixed_demo_ranges(self):
        entry = dataset.build_roster(1)[0]
        analytics, _ = dataset.build_dataset(entry, seed=7)
        for row in analytics["sales"]:
            assert row["transaction_date"].year in range(2024, 2027)


class TestReferentialIntegrity:
    def test_orders_reference_generated_customers_and_products(self):
        entry = dataset.build_roster(1)[0]
        analytics, _ = dataset.build_dataset(entry, seed=42)
        customers = {r["id"] for r in analytics["customers"]}
        products = {r["id"] for r in analytics["products"]}
        assert all(o["customer_id"] in customers for o in analytics["orders"])
        assert all(o["product_id"] in products for o in analytics["orders"])

    def test_sales_reference_generated_products_and_reps(self):
        entry = dataset.build_roster(1)[0]
        analytics, _ = dataset.build_dataset(entry, seed=42)
        products = {r["id"]: r["product_name"] for r in analytics["products"]}
        reps = {r["id"] for r in analytics["sales_representatives"]}
        for sale in analytics["sales"]:
            assert sale["product_id"] in products
            assert sale["product_name"] == products[sale["product_id"]]
            assert sale["rep_id"] in reps

    def test_activity_references_generated_web_users(self):
        entry = dataset.build_roster(1)[0]
        analytics, _ = dataset.build_dataset(entry, seed=42)
        web_users = {r["id"] for r in analytics["web_users"]}
        assert all(a["user_id"] in web_users for a in analytics["activity"])


class TestContent:
    def test_chart_spec_matches_the_reports_service_shape(self):
        entry = dataset.build_roster(1)[0]
        _, content = dataset.build_dataset(entry, seed=42)
        for section in content["report"]["sections"]:
            spec = section["chart_spec"]
            assert spec["chartType"] in ("Bar Chart", "Line Chart")
            assert set(spec["encodings"]) == {"x", "y"}
            assert spec["baseSize"] == {"width": 600, "height": 400}
            assert spec["data"]["values"]
            x_field = spec["encodings"]["x"]["field"]
            y_field = spec["encodings"]["y"]["field"]
            assert x_field in spec["data"]["values"][0]
            assert y_field in spec["data"]["values"][0]

    def test_chart_values_equal_aggregates_of_the_seeded_rows(self):
        entry = dataset.build_roster(1)[0]
        analytics, content = dataset.build_dataset(entry, seed=42)
        by_region: dict[str, float] = {}
        for sale in analytics["sales"]:
            by_region[sale["region"]] = by_region.get(sale["region"], 0.0) + sale["revenue"]
        region_section = content["report"]["sections"][0]
        values = {v["region"]: v["revenue"] for v in region_section["chart_spec"]["data"]["values"]}
        assert values == {k: round(v, 2) for k, v in by_region.items()}

    def test_narratives_quote_aggregate_numbers(self):
        entry = dataset.build_roster(1)[0]
        analytics, content = dataset.build_dataset(entry, seed=42)
        total = round(sum(s["revenue"] for s in analytics["sales"]), 2)
        assert f"{total:,.2f}" in content["report"]["sections"][0]["narrative"]
        assert f"{total:,.2f}" in content["conversation"]["messages"][1]["content"]

    def test_wiki_report_dashboard_conversation_present(self):
        entry = dataset.build_roster(1)[0]
        _, content = dataset.build_dataset(entry, seed=42)
        assert len(content["wiki_pages"]) >= 3
        assert len(content["report"]["sections"]) == 3
        assert content["dashboard"]["title"].startswith(entry["name"])
        assert content["conversation"]["messages"][0]["role"] == "user"
        assert content["conversation"]["messages"][1]["role"] == "assistant"

    def test_tuples_projection_matches_table_columns(self):
        entry = dataset.build_roster(1)[0]
        analytics, _ = dataset.build_dataset(entry, seed=42)
        for table, rows in analytics.items():
            tuples = dataset.tuples(rows, table)
            assert len(tuples) == len(rows)
            assert len(tuples[0]) == len(dataset.TABLE_COLUMNS[table])
            row0 = dict(zip(dataset.TABLE_COLUMNS[table], tuples[0], strict=True))
            assert row0["tenant_id"] == entry["tenant_id"]
