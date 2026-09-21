"""Reset env-key preservation + demo-marker parsing tests (offline)."""

from demo import common

from . import _SCRIPTS  # noqa: F401 — ensures scripts/ is on sys.path


class TestExtractPreservedKeys:
    def test_real_keys_are_preserved(self):
        env = (
            "ANTHROPIC_API_KEY=sk-ant-real123\n"
            "OPENAI_API_KEY=sk-proj-real456\n"
            "LANGFUSE_SECRET_KEY=lf-secret\n"
            "JWT_SECRET_KEY=abc123\n"
        )
        assert common.extract_preserved_keys(env) == {
            "ANTHROPIC_API_KEY": "sk-ant-real123",
            "OPENAI_API_KEY": "sk-proj-real456",
            "LANGFUSE_SECRET_KEY": "lf-secret",
        }

    def test_placeholders_are_not_preserved(self):
        env = (
            "ANTHROPIC_API_KEY=sk-ant-REPLACE-ME\n"
            "OPENAI_API_KEY=sk-REPLACE-ME\n"
            "LANGFUSE_PUBLIC_KEY=\n"
            "LANGFUSE_SECRET_KEY=changeme\n"
        )
        assert common.extract_preserved_keys(env) == {}

    def test_comments_blanks_and_unknown_keys_ignored(self):
        env = "# ANTHROPIC_API_KEY=sk-ant-real\n\nSOMETHING_ELSE=value\n"
        assert common.extract_preserved_keys(env) == {}

    def test_empty_text(self):
        assert common.extract_preserved_keys("") == {}


class TestInjectPreservedKeys:
    def test_replaces_placeholder_lines_in_place(self):
        fresh = (
            "# comment\n"
            "ANTHROPIC_API_KEY=sk-ant-REPLACE-ME\n"
            "OPENAI_API_KEY=sk-REPLACE-ME\n"
            "JWT_SECRET_KEY=fresh\n"
        )
        merged = common.inject_preserved_keys(
            fresh, {"ANTHROPIC_API_KEY": "sk-ant-real", "OPENAI_API_KEY": "sk-real"}
        )
        lines = dict(
            line.partition("=")[::2] for line in merged.splitlines() if "=" in line and not line.startswith("#")
        )
        assert lines["ANTHROPIC_API_KEY"] == "sk-ant-real"
        assert lines["OPENAI_API_KEY"] == "sk-real"
        assert lines["JWT_SECRET_KEY"] == "fresh"  # untouched by injection

    def test_appends_missing_keys(self):
        merged = common.inject_preserved_keys("A=1\n", {"OPENAI_API_KEY": "sk-real"})
        assert "OPENAI_API_KEY=sk-real" in merged.splitlines()

    def test_roundtrip_preserves_across_regeneration(self):
        old = "ANTHROPIC_API_KEY=sk-ant-real\nJWT_SECRET_KEY=old-secret\n"
        regenerated = "ANTHROPIC_API_KEY=sk-ant-REPLACE-ME\nJWT_SECRET_KEY=new-secret\n"
        keys = common.extract_preserved_keys(old)
        merged = common.inject_preserved_keys(regenerated, keys)
        assert "ANTHROPIC_API_KEY=sk-ant-real" in merged
        assert "JWT_SECRET_KEY=new-secret" in merged
        assert "old-secret" not in merged


class TestDemoMarkerParsing:
    def test_parses_psql_output(self):
        raw = (
            "e3b0c442-0000-0000-0000-000000000001|Acme Analytics|demo-acme|42|2026-09-21T10:00:00+00:00\n"
            "e3b0c442-0000-0000-0000-000000000002|Globex Retail|demo-globex|42|2026-09-21T10:01:00+00:00\n"
        )
        tenants = common.parse_demo_tenants(raw)
        assert [t["slug"] for t in tenants] == ["demo-acme", "demo-globex"]
        assert tenants[0]["seed"] == "42"

    def test_empty_output_yields_no_tenants(self):
        assert common.parse_demo_tenants("") == []
        assert common.parse_demo_tenants("\n \n") == []

    def test_malformed_lines_are_skipped(self):
        raw = "only-one-field\nid|name|slug|seed\n"
        assert common.parse_demo_tenants(raw) == []
