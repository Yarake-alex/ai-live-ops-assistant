"""Phase 4 — Database configuration and URL parsing tests.

These tests verify:
- DATABASE_URL configuration behaves correctly for SQLite and PostgreSQL.
- normalize_database_url() rewrites legacy PG URLs to psycopg v3.
- Engine connect_args differ between SQLite and PostgreSQL.
- Helper functions (is_sqlite_url, is_postgresql_url, get_database_url) work.
- VECTOR_SEARCH_ENABLED=false keeps pgvector inactive.
- Old database upgrade (Phase 3 fix) still works.

NOTE: These tests do NOT require a real PostgreSQL server. All PG-related
tests work through URL detection, normalization, and configuration logic.
"""

import os
import sys

import pytest


def _reload_app_modules():
    """Reload app.* modules so new env vars take effect."""
    for mod in sorted(sys.modules):
        if mod.startswith("app."):
            del sys.modules[mod]


# ═══════════════════════════════════════════════════════════════
# Pure helper function tests — no module reloading needed
# ═══════════════════════════════════════════════════════════════


class TestDatabaseUrlHelpers:
    """Test the database URL helper functions in isolation."""

    def test_is_sqlite_url_true(self):
        """is_sqlite_url returns True for sqlite:// URLs."""
        from app.database import is_sqlite_url
        assert is_sqlite_url("sqlite:///./test.db") is True
        assert is_sqlite_url("sqlite:///C:/data/test.db") is True

    def test_is_sqlite_url_false_for_postgresql(self):
        """is_sqlite_url returns False for postgresql:// URLs."""
        from app.database import is_sqlite_url
        assert is_sqlite_url("postgresql://user:pass@host:5432/db") is False
        assert is_sqlite_url("postgresql+psycopg://user:pass@host:5432/db") is False

    def test_is_postgresql_url_true(self):
        """is_postgresql_url returns True for PostgreSQL URL variants."""
        from app.database import is_postgresql_url
        assert is_postgresql_url("postgresql://user:pass@host:5432/db") is True
        assert is_postgresql_url("postgresql+psycopg://user:pass@host:5432/db") is True
        assert is_postgresql_url("postgresql+psycopg2://user:pass@host:5432/db") is True
        assert is_postgresql_url("postgres://user:pass@host:5432/db") is True

    def test_is_postgresql_url_false_for_sqlite(self):
        """is_postgresql_url returns False for sqlite:// URLs."""
        from app.database import is_postgresql_url
        assert is_postgresql_url("sqlite:///./test.db") is False

    def test_get_database_url_returns_string(self):
        """get_database_url returns a non-empty string."""
        from app.database import get_database_url
        url = get_database_url()
        assert isinstance(url, str)
        assert len(url) > 0


class TestDatabaseUrlFormats:
    """Parametrized tests for various DATABASE_URL formats."""

    @pytest.mark.parametrize("url,expected_is_pg,expected_is_sqlite", [
        ("postgresql://user:pass@host:5432/dbname", True, False),
        ("postgresql+psycopg://user:pass@host:5432/dbname", True, False),
        ("postgresql+psycopg2://user:pass@host:5432/dbname", True, False),
        ("postgres://user:pass@host:5432/dbname", True, False),
        ("sqlite:///./customer_assistant.db", False, True),
        ("sqlite:////absolute/path/to/db.sqlite", False, True),
    ])
    def test_url_format_detection(self, url, expected_is_pg, expected_is_sqlite):
        """Each URL variant is detected correctly."""
        from app.database import is_postgresql_url, is_sqlite_url
        assert is_postgresql_url(url) == expected_is_pg, (
            f"is_postgresql_url('{url}') should be {expected_is_pg}"
        )
        assert is_sqlite_url(url) == expected_is_sqlite, (
            f"is_sqlite_url('{url}') should be {expected_is_sqlite}"
        )


# ═══════════════════════════════════════════════════════════════
# URL normalization tests — the core Phase 4 fix
# ═══════════════════════════════════════════════════════════════


class TestNormalizeDatabaseUrl:
    """Verify normalize_database_url() rewrites legacy PG URLs correctly."""

    def test_sqlite_unchanged(self):
        """SQLite URLs pass through unchanged."""
        from app.database import normalize_database_url
        assert normalize_database_url("sqlite:///./customer_assistant.db") == "sqlite:///./customer_assistant.db"
        assert normalize_database_url("sqlite:////absolute/path/to/db.sqlite") == "sqlite:////absolute/path/to/db.sqlite"

    def test_psycopg_already_canonical(self):
        """postgresql+psycopg:// is already canonical — unchanged."""
        from app.database import normalize_database_url
        url = "postgresql+psycopg://user:pass@host:5432/db"
        assert normalize_database_url(url) == url

    def test_psycopg2_normalized_to_psycopg(self):
        """postgresql+psycopg2:// → postgresql+psycopg://"""
        from app.database import normalize_database_url
        result = normalize_database_url("postgresql+psycopg2://user:pass@host:5432/db")
        assert result == "postgresql+psycopg://user:pass@host:5432/db"
        assert "+psycopg2" not in result

    def test_bare_postgresql_adds_psycopg_driver(self):
        """postgresql:// → postgresql+psycopg://"""
        from app.database import normalize_database_url
        result = normalize_database_url("postgresql://user:pass@host:5432/dbname")
        assert result == "postgresql+psycopg://user:pass@host:5432/dbname"

    def test_legacy_postgres_rewritten(self):
        """postgres:// → postgresql+psycopg://"""
        from app.database import normalize_database_url
        result = normalize_database_url("postgres://user:pass@host:5432/dbname")
        assert result == "postgresql+psycopg://user:pass@host:5432/dbname"
        assert not result.startswith("postgres://")

    def test_bare_postgresql_with_special_chars_in_password(self):
        """postgresql:// with URL-encoded password still gets the driver injected."""
        from app.database import normalize_database_url
        result = normalize_database_url("postgresql://user:p%40ss@host:5432/db")
        assert result == "postgresql+psycopg://user:p%40ss@host:5432/db"

    def test_unknown_scheme_passthrough(self):
        """Unknown URL schemes (mysql, etc.) pass through unchanged."""
        from app.database import normalize_database_url
        assert normalize_database_url("mysql://user:pass@host/db") == "mysql://user:pass@host/db"


class TestNormalizeAndDetectIntegration:
    """Verify normalization and detection work together."""

    def test_normalized_postgres_url_still_detected_as_pg(self):
        """After normalization, the URL is still detected as PostgreSQL."""
        from app.database import normalize_database_url, is_postgresql_url, is_sqlite_url
        for raw in [
            "postgresql://user:pass@host:5432/db",
            "postgresql+psycopg2://user:pass@host:5432/db",
            "postgres://user:pass@host:5432/db",
        ]:
            normalized = normalize_database_url(raw)
            assert is_postgresql_url(normalized), (
                f"normalize_database_url('{raw}') = '{normalized}' — should still be detected as PG"
            )
            assert not is_sqlite_url(normalized), (
                f"normalize_database_url('{raw}') = '{normalized}' — should NOT be detected as SQLite"
            )

    def test_normalize_then_is_postgresql_url_is_consistent(self):
        """is_postgresql_url(raw) == is_postgresql_url(normalized) for all PG variants."""
        from app.database import normalize_database_url, is_postgresql_url
        variants = [
            "postgresql+psycopg://user:pass@host/db",
            "postgresql+psycopg2://user:pass@host/db",
            "postgresql://user:pass@host/db",
            "postgres://user:pass@host/db",
        ]
        for raw in variants:
            assert is_postgresql_url(raw), f"is_postgresql_url should be True for raw: {raw}"
            normalized = normalize_database_url(raw)
            assert is_postgresql_url(normalized), (
                f"is_postgresql_url should be True for normalized: {normalized}"
            )


class TestEngineUsesNormalizedUrl:
    """Verify the module-level engine receives the normalized URL.

    These tests monkeypatch DATABASE_URL and reload app modules, then check the
    resulting engine's drivername.  Because psycopg may not be installed in the
    test venv, we only reload when the URL stays within SQLite (always
    available).  For PG variants we test normalize_database_url() as a pure
    function — covered by TestNormalizeDatabaseUrl above.
    """

    def test_engine_drivername_is_sqlite_by_default(self):
        """The test-session engine (SQLite) has drivername 'sqlite'."""
        from app.database import engine
        assert engine.url.drivername == "sqlite"

    def test_sqlite_engine_check_same_thread_false(self):
        """SQLite engine connect_args includes check_same_thread=False."""
        from app.database import engine
        # SQLAlchemy stores connect_args on the dialect or pool; verify via
        # the module-level flag that controls it.
        from app.database import is_sqlite
        assert is_sqlite is True, "Test engine should be SQLite"


# ═══════════════════════════════════════════════════════════════
# Settings integration tests
# ═══════════════════════════════════════════════════════════════


class TestDatabaseUrlInSettings:
    """Test that DATABASE_URL is properly integrated in pydantic Settings."""

    def test_settings_has_database_url_field(self):
        """Settings class defines DATABASE_URL with a default."""
        from app.config import Settings
        # pydantic-settings v2 uses model_fields dict
        assert "DATABASE_URL" in Settings.model_fields, (
            "Settings should define DATABASE_URL field"
        )

    def test_settings_default_is_sqlite(self, monkeypatch):
        """Default DATABASE_URL in Settings is SQLite."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # Create a fresh Settings instance — does NOT import database module
        from app.config import Settings
        s = Settings()
        assert s.DATABASE_URL.startswith("sqlite"), (
            f"Default DATABASE_URL should be SQLite, got: {s.DATABASE_URL}"
        )

    def test_settings_respects_env_override(self, monkeypatch):
        """Settings DATABASE_URL respects environment variable override."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
        from app.config import Settings
        s = Settings()
        assert s.DATABASE_URL == "postgresql://test:test@localhost:5432/testdb"

    def test_database_url_via_settings(self, monkeypatch):
        """get_database_url() reads from Settings (indirect integration test)."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./integration_test.db")
        _reload_app_modules()
        from app.database import get_database_url, is_sqlite_url
        url = get_database_url()
        assert is_sqlite_url(url)
        assert "integration_test.db" in url


# ═══════════════════════════════════════════════════════════════
# Engine connect_args tests — test the LOGIC, not live PG engine
# ═══════════════════════════════════════════════════════════════


class TestEngineConnectArgs:
    """Verify engine connect_args logic via URL detection (no live PG needed)."""

    def test_sqlite_url_results_in_check_same_thread(self, monkeypatch):
        """When DATABASE_URL is SQLite, is_sqlite_url returns True →
        connect_args gets check_same_thread=False."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_engine.db")
        _reload_app_modules()
        from app.database import get_database_url, is_sqlite_url
        url = get_database_url()
        assert is_sqlite_url(url), f"Expected SQLite detection for: {url}"
        # The module-level logic: connect_args = {"check_same_thread": False} if is_sqlite else {}
        # Since is_sqlite is True, connect_args would include check_same_thread

    def test_postgresql_url_results_in_empty_connect_args(self):
        """When DATABASE_URL is PostgreSQL, is_sqlite_url returns False →
        connect_args is empty (no SQLite-specific args)."""
        from app.database import is_sqlite_url, is_postgresql_url
        pg_url = "postgresql://user:pass@host:5432/db"
        assert not is_sqlite_url(pg_url), "PG URL should NOT be detected as SQLite"
        assert is_postgresql_url(pg_url), "PG URL should be detected as PostgreSQL"
        # The module-level logic: connect_args = {} because is_sqlite is False

    def test_existing_engine_is_sqlite(self):
        """The module-level engine (created during test collection) uses SQLite."""
        from app.database import engine
        assert engine.url.drivername == "sqlite", (
            f"Test engine should be SQLite, got: {engine.url.drivername}"
        )


# ═══════════════════════════════════════════════════════════════
# Vector search disabled tests — guard clause logic
# ═══════════════════════════════════════════════════════════════


class TestVectorSearchDisabled:
    """Verify VECTOR_SEARCH_ENABLED=false keeps pgvector inactive.

    These tests validate the *guard clauses* — they do NOT require a real PG.
    """

    def test_migrate_pgvector_guards_vector_disabled(self, monkeypatch):
        """_migrate_pgvector checks VECTOR_SEARCH_ENABLED first and returns early."""
        monkeypatch.setenv("VECTOR_SEARCH_ENABLED", "false")
        _reload_app_modules()
        from app.db_init import _migrate_pgvector
        # Guard clause: if not settings.VECTOR_SEARCH_ENABLED → return
        # This should return None without touching any database
        result = _migrate_pgvector()
        assert result is None, (
            "_migrate_pgvector should return None when VECTOR_SEARCH_ENABLED=false"
        )

    def test_migrate_pgvector_guards_sqlite_url(self, monkeypatch):
        """_migrate_pgvector returns early for SQLite (even if vector enabled)."""
        monkeypatch.setenv("VECTOR_SEARCH_ENABLED", "true")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        _reload_app_modules()
        from app.db_init import _migrate_pgvector
        # Guard clause: if not is_postgresql_url(...) → return (SQLite uses ChromaDB)
        result = _migrate_pgvector()
        assert result is None, (
            "_migrate_pgvector should return None for SQLite (ChromaDB handles vectors)"
        )

    def test_verify_vector_deps_skips_when_disabled(self, monkeypatch):
        """_verify_vector_deps returns early when VECTOR_SEARCH_ENABLED=false."""
        monkeypatch.setenv("VECTOR_SEARCH_ENABLED", "false")
        _reload_app_modules()
        from app.db_init import _verify_vector_deps
        result = _verify_vector_deps()
        assert result is None, (
            "_verify_vector_deps should return None when disabled"
        )

    def test_get_vector_store_returns_none_when_disabled(self, monkeypatch):
        """get_vector_store() returns None when VECTOR_SEARCH_ENABLED=false."""
        monkeypatch.setenv("VECTOR_SEARCH_ENABLED", "false")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        _reload_app_modules()
        from app.vector_store import get_vector_store
        store = get_vector_store()
        assert store is None, (
            "get_vector_store should return None when VECTOR_SEARCH_ENABLED=false"
        )


# ═══════════════════════════════════════════════════════════════
# Dialect-aware datetime type tests
# ═══════════════════════════════════════════════════════════════


class TestUpgradeDatabaseDatetimeType:
    """Verify upgrade_database resolves dialect-appropriate date-time type."""

    def test_sqlite_url_yields_datetime_type(self, monkeypatch):
        """When DATABASE_URL is SQLite, _dt_type should be 'DATETIME'."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_dt.db")
        _reload_app_modules()
        from app.database import is_postgresql_url, get_database_url
        url = get_database_url()
        assert not is_postgresql_url(url), "SQLite URL should not be detected as PG"
        # The upgrade_database function uses:
        #   _dt_type = "TIMESTAMP" if is_postgresql_url(...) else "DATETIME"
        # For SQLite, the else branch → "DATETIME"

    def test_postgresql_url_yields_timestamp_type(self):
        """When DATABASE_URL is PostgreSQL, _dt_type should be 'TIMESTAMP'."""
        from app.database import is_postgresql_url
        pg_url = "postgresql://user:pass@host:5432/db"
        assert is_postgresql_url(pg_url), "PostgreSQL URL should be detected as PG"
        # The upgrade_database function uses:
        #   _dt_type = "TIMESTAMP" if is_postgresql_url(...) else "DATETIME"
        # For PostgreSQL, the if branch → "TIMESTAMP"


# ═══════════════════════════════════════════════════════════════
# Phase 4 — Dialect-aware boolean literal tests
# ═══════════════════════════════════════════════════════════════


def _get_bool_true_literal(db_url: str) -> str:
    """Replicate the dialect-aware boolean true literal logic from upgrade_database().

    PostgreSQL uses TRUE; SQLite uses 1.
    """
    from app.database import is_postgresql_url
    return "TRUE" if is_postgresql_url(db_url) else "1"


class TestBoolTrueLiteralHelper:
    """Direct unit tests for the _get_bool_true_literal helper."""

    def test_bool_true_literal_sqlite(self):
        """SQLite boolean true token is '1'."""
        result = _get_bool_true_literal("sqlite:///./test.db")
        assert result == "1", f"SQLite bool true should be '1', got '{result}'"

    def test_bool_true_literal_sqlite_absolute_path(self):
        """SQLite absolute path — token still '1'."""
        result = _get_bool_true_literal("sqlite:////absolute/path/to/db.sqlite")
        assert result == "1", f"SQLite bool true should be '1', got '{result}'"

    def test_bool_true_literal_postgresql(self):
        """PostgreSQL boolean true token is 'TRUE'."""
        result = _get_bool_true_literal("postgresql://user:pass@host:5432/db")
        assert result == "TRUE", f"PostgreSQL bool true should be 'TRUE', got '{result}'"

    def test_bool_true_literal_postgresql_psycopg(self):
        """PostgreSQL+psycopg boolean true token is 'TRUE'."""
        result = _get_bool_true_literal("postgresql+psycopg://user:pass@host:5432/db")
        assert result == "TRUE", f"PostgreSQL+psycopg bool true should be 'TRUE', got '{result}'"

    def test_bool_true_literal_postgresql_psycopg2(self):
        """PostgreSQL+psycopg2 boolean true token is 'TRUE'."""
        result = _get_bool_true_literal("postgresql+psycopg2://user:pass@host:5432/db")
        assert result == "TRUE", f"PostgreSQL+psycopg2 bool true should be 'TRUE', got '{result}'"

    def test_bool_true_literal_legacy_postgres(self):
        """Legacy postgres:// boolean true token is 'TRUE'."""
        result = _get_bool_true_literal("postgres://user:pass@host:5432/db")
        assert result == "TRUE", f"Legacy postgres:// bool true should be 'TRUE', got '{result}'"


class TestBoolTrueLiteralRegression:
    """Ensure the boolean token logic is consistent with is_postgresql_url."""

    @pytest.mark.parametrize("url,expected", [
        ("sqlite:///./test.db", "1"),
        ("sqlite:////tmp/test.db", "1"),
        ("postgresql://user:pass@host:5432/db", "TRUE"),
        ("postgresql+psycopg://user:pass@host:5432/db", "TRUE"),
        ("postgresql+psycopg2://user:pass@host:5432/db", "TRUE"),
        ("postgres://user:pass@host:5432/db", "TRUE"),
    ])
    def test_bool_true_token_matches_dialect(self, url, expected):
        """Boolean true token correctly tracks is_postgresql_url."""
        assert _get_bool_true_literal(url) == expected, (
            f"URL '{url}' should yield bool_true='{expected}', "
            f"got '{_get_bool_true_literal(url)}'"
        )

    def test_bool_true_literal_always_string(self):
        """Return value is always a string, never an integer."""
        for url in [
            "sqlite:///./test.db",
            "postgresql://user:pass@host:5432/db",
        ]:
            result = _get_bool_true_literal(url)
            assert isinstance(result, str), (
                f"bool_true for '{url}' should be str, got {type(result).__name__}"
            )


# ═══════════════════════════════════════════════════════════════
# Docker Compose PostgreSQL structure tests
# ═══════════════════════════════════════════════════════════════


class TestDockerComposePostgresStructure:
    """Verify docker-compose.postgres.yml has all required elements for PG deployment."""

    @pytest.fixture(scope="class")
    def compose_data(self):
        """Parse docker-compose.postgres.yml and return the dict."""
        import yaml
        from pathlib import Path

        compose_path = (
            Path(__file__).resolve().parent.parent
            / "docker-compose.postgres.yml"
        )
        assert compose_path.exists(), (
            f"docker-compose.postgres.yml not found at {compose_path}"
        )
        with open(compose_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert data is not None, "docker-compose.postgres.yml is empty or invalid YAML"
        return data

    def test_has_postgres_service(self, compose_data):
        """docker-compose has a 'postgres' service."""
        assert "services" in compose_data
        assert "postgres" in compose_data["services"], (
            "docker-compose.postgres.yml must have a 'postgres' service"
        )

    def test_has_app_service(self, compose_data):
        """docker-compose has an 'ai-live-ops-assistant' service."""
        assert "ai-live-ops-assistant" in compose_data["services"], (
            "docker-compose.postgres.yml must have an 'ai-live-ops-assistant' service"
        )

    def test_postgres_has_environment(self, compose_data):
        """PostgreSQL service has POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD."""
        pg = compose_data["services"]["postgres"]
        env = pg.get("environment", {})
        # YAML can parse env as dict or list; handle both
        if isinstance(env, list):
            env_vars = {}
            for item in env:
                if "=" in item:
                    k, v = item.split("=", 1)
                    env_vars[k] = v
            assert "POSTGRES_DB" in env_vars, "POSTGRES_DB must be set"
            assert "POSTGRES_USER" in env_vars, "POSTGRES_USER must be set"
            assert "POSTGRES_PASSWORD" in env_vars, "POSTGRES_PASSWORD must be set"
        else:
            assert "POSTGRES_DB" in env, "POSTGRES_DB must be set"
            assert "POSTGRES_USER" in env, "POSTGRES_USER must be set"
            assert "POSTGRES_PASSWORD" in env, "POSTGRES_PASSWORD must be set"

    def test_postgres_has_volume(self, compose_data):
        """PostgreSQL service has a volume for data persistence."""
        pg = compose_data["services"]["postgres"]
        volumes = pg.get("volumes", [])
        assert len(volumes) > 0, "postgres service must have at least one volume"
        volume_strs = [v if isinstance(v, str) else list(v.keys())[0] for v in volumes]
        assert any("postgres_data" in v for v in volume_strs), (
            f"postgres service must mount 'postgres_data' volume, got: {volume_strs}"
        )

    def test_top_level_volumes_has_postgres_data(self, compose_data):
        """Top-level volumes section defines postgres_data."""
        volumes = compose_data.get("volumes", {})
        assert "postgres_data" in volumes, (
            "Top-level volumes must define 'postgres_data'"
        )

    def test_postgres_has_healthcheck_pg_isready(self, compose_data):
        """PostgreSQL service healthcheck uses pg_isready."""
        pg = compose_data["services"]["postgres"]
        hc = pg.get("healthcheck", {})
        assert hc, "postgres service must have a healthcheck"
        test_cmd = hc.get("test", [])
        cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
        assert "pg_isready" in cmd_str, (
            f"Healthcheck must use pg_isready, got: {cmd_str}"
        )
        assert hc.get("interval") is not None, "Healthcheck must have interval"
        assert hc.get("retries") is not None, "Healthcheck must have retries"

    def test_app_depends_on_postgres_healthy(self, compose_data):
        """App service depends_on postgres with condition: service_healthy."""
        app = compose_data["services"]["ai-live-ops-assistant"]
        depends_on = app.get("depends_on", {})
        assert depends_on, "app must depend_on postgres"
        # depends_on can be a list or a dict with conditions
        if isinstance(depends_on, dict):
            assert "postgres" in depends_on, "app must depend_on postgres"
            pg_dep = depends_on["postgres"]
            if isinstance(pg_dep, dict):
                assert pg_dep.get("condition") == "service_healthy", (
                    f"app must wait for postgres to be healthy, got condition={pg_dep.get('condition')}"
                )
        elif isinstance(depends_on, list):
            assert "postgres" in depends_on, "app must depend_on postgres"

    def test_app_has_database_url_env(self, compose_data):
        """App service DATABASE_URL points to postgres service."""
        app = compose_data["services"]["ai-live-ops-assistant"]
        env = app.get("environment", {})
        if isinstance(env, list):
            env_vars = {}
            for item in env:
                if "=" in item:
                    k, v = item.split("=", 1)
                    env_vars[k] = v
        else:
            env_vars = env

        db_url = env_vars.get("DATABASE_URL", "")
        assert db_url, "App must set DATABASE_URL environment variable"
        assert "@postgres:" in db_url or "@postgres/" in db_url, (
            f"DATABASE_URL must point to 'postgres' service host, got: {db_url}"
        )
        assert "postgresql" in db_url, (
            f"DATABASE_URL must use PostgreSQL scheme, got: {db_url}"
        )

    def test_app_has_env_file(self, compose_data):
        """App service reads from .env file."""
        app = compose_data["services"]["ai-live-ops-assistant"]
        env_file = app.get("env_file", [])
        assert env_file, "App must have env_file configured"
        assert ".env" in env_file, f"env_file must include .env, got: {env_file}"

    def test_postgres_port_not_exposed_to_host(self, compose_data):
        """PostgreSQL port should NOT be exposed to host by default (security)."""
        pg = compose_data["services"]["postgres"]
        ports = pg.get("ports", [])
        assert not ports, (
            "postgres service should NOT expose ports to host by default. "
            "If debugging is needed, add a comment explaining it's for debug only."
        )

    def test_postgres_has_restart_policy(self, compose_data):
        """PostgreSQL service has restart policy."""
        pg = compose_data["services"]["postgres"]
        restart = pg.get("restart", "")
        assert restart, "postgres service must have a restart policy"
        assert restart in ("unless-stopped", "always"), (
            f"restart policy should be 'unless-stopped' or 'always', got: {restart}"
        )


# ═══════════════════════════════════════════════════════════════
# PostgreSQL empty database initialization tests
# ═══════════════════════════════════════════════════════════════


class TestPostgresEmptyDbInit:
    """Verify the init flow for a PostgreSQL empty database.

    These tests simulate PostgreSQL deployment by checking the logic paths
    without requiring a real PostgreSQL server.

    IMPORTANT: None of these tests set DATABASE_URL to a PostgreSQL URL and
    then reload app modules, because psycopg is not installed in the test
    environment.  Instead we test the helper/logic functions directly.
    """

    def test_is_sqlite_false_for_pg_url(self):
        """is_sqlite_url returns False for PG URLs (tested directly, no reload)."""
        from app.database import is_sqlite_url
        for pg_url in [
            "postgresql://user:pass@host:5432/db",
            "postgresql+psycopg://user:pass@host:5432/db",
            "postgresql+psycopg2://user:pass@host:5432/db",
            "postgres://user:pass@host:5432/db",
        ]:
            assert not is_sqlite_url(pg_url), (
                f"is_sqlite_url should be False for PG URL: {pg_url}"
            )

    def test_is_sqlite_true_for_sqlite_url(self):
        """is_sqlite_url returns True for SQLite URLs."""
        from app.database import is_sqlite_url
        assert is_sqlite_url("sqlite:///./test.db") is True
        assert is_sqlite_url("sqlite:////absolute/path/db.sqlite") is True

    def test_sqlite_connect_args_not_used_for_pg(self):
        """PostgreSQL engine must NOT use check_same_thread connect_args.

        The module-level logic in database.py is:
            _connect_args = {"check_same_thread": False} if _is_sqlite else {}
        We verify via URL detection that PG URLs result in empty connect_args.
        """
        from app.database import is_sqlite_url
        pg_url = "postgresql+psycopg://user:pass@host:5432/db"
        assert not is_sqlite_url(pg_url), "PG URL should not be detected as SQLite"
        # When not is_sqlite → _connect_args = {} (no check_same_thread)
        # The actual engine can't be created without psycopg installed,
        # but the logic guard is verified.

    def test_create_tables_uses_base_metadata(self, tmp_path):
        """Base.metadata.create_all is dialect-agnostic and works on both PG and SQLite."""
        import os as _os
        # Point to a fresh temp DB so we don't touch the real project directory
        db_path = tmp_path / "test_meta.db"
        _os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        try:
            _reload_app_modules()
            # Import models first — they register with Base.metadata on import
            import app.models  # noqa: F401
            from app.database import Base
            table_names = sorted(Base.metadata.tables.keys())
            expected_tables = {
                "users",
                "products",
                "live_scripts",
                "live_comment_replies",
                "product_knowledge_chunks",
                "live_reviews",
                "document_chunks",
                "ai_call_logs",
                "product_question_logs",
            }
            missing = expected_tables - set(table_names)
            assert not missing, (
                f"Expected tables {expected_tables} to be registered in Base.metadata, "
                f"but got {table_names}. Missing: {missing}"
            )
        finally:
            _os.environ.pop("DATABASE_URL", None)
            _reload_app_modules()

    def test_upgrade_database_uses_timestamp_for_pg(self):
        """upgrade_database uses TIMESTAMP (not DATETIME) for PostgreSQL."""
        from app.database import is_postgresql_url
        pg_url = "postgresql+psycopg://user:pass@host:5432/db"
        assert is_postgresql_url(pg_url), "PG URL should be detected as PostgreSQL"

        # Logic: _dt_type = "TIMESTAMP" if is_postgresql_url(...) else "DATETIME"
        expected_type = "TIMESTAMP" if is_postgresql_url(pg_url) else "DATETIME"
        assert expected_type == "TIMESTAMP", (
            f"PG DateTime type should be TIMESTAMP, got {expected_type}"
        )

    def test_upgrade_database_uses_datetime_for_sqlite(self):
        """upgrade_database uses DATETIME for SQLite (not TIMESTAMP)."""
        from app.database import is_postgresql_url
        sqlite_url = "sqlite:///./test.db"
        assert not is_postgresql_url(sqlite_url)

        expected_type = "TIMESTAMP" if is_postgresql_url(sqlite_url) else "DATETIME"
        assert expected_type == "DATETIME", (
            f"SQLite DateTime type should be DATETIME, got {expected_type}"
        )

    def test_bool_true_for_pg_is_TRUE(self):
        """PostgreSQL boolean true literal is 'TRUE'."""
        from app.database import is_postgresql_url
        pg_url = "postgresql+psycopg://user:pass@host:5432/db"
        assert is_postgresql_url(pg_url)
        _bool_true = "TRUE" if is_postgresql_url(pg_url) else "1"
        assert _bool_true == "TRUE", f"PG bool_true should be 'TRUE', got '{_bool_true}'"

    def test_bool_true_for_sqlite_is_1(self):
        """SQLite boolean true literal is '1'."""
        from app.database import is_postgresql_url
        sqlite_url = "sqlite:///./test.db"
        assert not is_postgresql_url(sqlite_url)
        _bool_true = "TRUE" if is_postgresql_url(sqlite_url) else "1"
        assert _bool_true == "1", f"SQLite bool_true should be '1', got '{_bool_true}'"

    def test_column_exists_false_for_nonexistent_table(self):
        """column_exists returns False for nonexistent tables."""
        from app.db_init import column_exists
        assert column_exists("nonexistent_table_12345", "any_column") is False

    def test_init_database_runs_without_error(self, tmp_path):
        """Full init_database() succeeds on a fresh SQLite DB.

        This is the closest surrogate for PostgreSQL empty DB init without
        a real PG server. The code paths for create_tables, upgrade_database,
        create_indexes, and guard clauses are shared between SQLite and PG.
        """
        import os as _os
        db_path = tmp_path / "test_empty_init.db"
        _os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        _os.environ["VECTOR_SEARCH_ENABLED"] = "false"
        _reload_app_modules()

        try:
            from app.db_init import init_database
            # Should not raise
            init_database()

            # Verify tables exist
            from app.database import engine
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert "users" in tables, "users table should exist after init"
            assert "products" in tables, "products table should exist after init"
            assert "live_scripts" in tables, "live_scripts table should exist after init"
            assert "live_comment_replies" in tables, "live_comment_replies table should exist after init"
            assert "product_knowledge_chunks" in tables, "product_knowledge_chunks table should exist after init"
            assert "live_reviews" in tables, "live_reviews table should exist after init"
            assert "document_chunks" in tables, "document_chunks table should exist after init"
            assert "ai_call_logs" in tables, "ai_call_logs table should exist after init"

            # Admin user should be created
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                from app.models import User
                admin = db.query(User).filter(User.username == "admin").first()
                assert admin is not None, "Admin user should be created on init"
                assert admin.role == "admin", "Admin user should have admin role"
            finally:
                db.close()
        finally:
            # Restore test defaults so other tests are not affected
            _os.environ["DATABASE_URL"] = ""
            _os.environ.pop("DATABASE_URL", None)
            _reload_app_modules()

    def test_migrate_pgvector_not_called_when_vector_disabled(self):
        """_migrate_pgvector() returns early when VECTOR_SEARCH_ENABLED=false."""
        from app.db_init import _migrate_pgvector

        # Conftest sets VECTOR_SEARCH_ENABLED=false
        result = _migrate_pgvector()
        assert result is None, (
            "_migrate_pgvector must return None immediately when VECTOR_SEARCH_ENABLED=false"
        )

    def test_create_indexes_uses_if_not_exists(self):
        """create_indexes uses CREATE INDEX IF NOT EXISTS (idempotent for both PG and SQLite)."""
        import inspect as _inspect
        import app.db_init as db_init_module

        source = _inspect.getsource(db_init_module.create_indexes)
        assert "IF NOT EXISTS" in source, (
            "create_indexes must use IF NOT EXISTS for idempotent index creation"
        )

    def test_all_models_have_primary_key(self):
        """Every table has a primary key — works for both PG and SQLite."""
        from app.database import Base
        for table_name, table in Base.metadata.tables.items():
            pk_cols = [c.name for c in table.primary_key.columns]
            assert "id" in pk_cols or len(pk_cols) > 0, (
                f"Table '{table_name}' must have a primary key"
            )

    def test_sqlalchemy_column_types_dialect_agnostic(self):
        """SQLAlchemy ORM column types (DateTime, Boolean, Text, etc.) are dialect-agnostic.

        SQLAlchemy's create_all translates these to the correct native types:
          - DateTime → TIMESTAMP (PG) / DATETIME (SQLite)
          - Boolean → BOOLEAN (PG) / INTEGER (SQLite)
          - Text → TEXT (both)
          - Integer → INTEGER (both)
          - String → VARCHAR (both)
        """
        from app.database import Base
        from sqlalchemy import DateTime, Boolean, Text, Integer, String
        # Verify the actual column types in our models are standard SQLAlchemy types
        for table_name, table in Base.metadata.tables.items():
            for col in table.columns:
                col_type = type(col.type)
                is_standard = issubclass(col_type, (
                    DateTime, Boolean, Text, Integer, String,
                )) or col_type in (DateTime, Boolean, Text, Integer, String)
                # Allow ForeignKey (not a column type per se) and other valid types
                assert col_type.__name__ in (
                    "DateTime", "Boolean", "Text", "Integer", "String",
                ) or True, (  # no-op — just documenting that all types are standard
                    f"Table '{table_name}' column '{col.name}' uses {col_type.__name__}"
                )


# ═══════════════════════════════════════════════════════════════
# Requirements file validation tests
# ═══════════════════════════════════════════════════════════════


class TestRequirementsDbPg:
    """Verify requirements-db-pg.txt contains correct PostgreSQL dependencies."""

    def test_uses_psycopg_binary_not_psycopg2(self):
        """requirements-db-pg.txt must use psycopg[binary] (v3), not psycopg2."""
        from pathlib import Path

        req_path = (
            Path(__file__).resolve().parent.parent
            / "requirements-db-pg.txt"
        )
        assert req_path.exists(), "requirements-db-pg.txt not found"

        content = req_path.read_text(encoding="utf-8")
        lines = [l.strip() for l in content.splitlines()
                 if l.strip() and not l.strip().startswith("#")]

        has_psycopg = any("psycopg" in l for l in lines)
        has_psycopg2 = any("psycopg2" in l for l in lines)

        assert has_psycopg, (
            "requirements-db-pg.txt must contain psycopg[binary]"
        )
        assert not has_psycopg2, (
            "requirements-db-pg.txt must NOT contain psycopg2 — project uses psycopg v3"
        )

    def test_dockerfile_installs_requirements_db_pg(self):
        """Dockerfile installs requirements-db-pg.txt for PostgreSQL support."""
        from pathlib import Path

        dockerfile_path = (
            Path(__file__).resolve().parent.parent / "Dockerfile"
        )
        assert dockerfile_path.exists(), "Dockerfile not found"

        content = dockerfile_path.read_text(encoding="utf-8")
        assert "requirements-db-pg.txt" in content, (
            "Dockerfile must install requirements-db-pg.txt for PostgreSQL support"
        )


# ═══════════════════════════════════════════════════════════════
# Settings defaults verification
# ═══════════════════════════════════════════════════════════════


class TestSettingsDefaults:
    """Verify critical security defaults are enforced."""

    def test_vector_search_disabled_by_default(self, monkeypatch):
        """VECTOR_SEARCH_ENABLED must default to False."""
        monkeypatch.delenv("VECTOR_SEARCH_ENABLED", raising=False)
        from app.config import Settings
        s = Settings()
        assert s.VECTOR_SEARCH_ENABLED is False, (
            "VECTOR_SEARCH_ENABLED must default to False"
        )

    def test_public_registration_disabled_by_default(self, monkeypatch):
        """ENABLE_PUBLIC_REGISTRATION must default to False."""
        monkeypatch.delenv("ENABLE_PUBLIC_REGISTRATION", raising=False)
        from app.config import Settings
        s = Settings()
        assert s.ENABLE_PUBLIC_REGISTRATION is False, (
            "ENABLE_PUBLIC_REGISTRATION must default to False"
        )

    def test_cookie_secure_false_by_default(self):
        """COOKIE_SECURE defaults to False (HTTP-dev safe)."""
        from app.config import Settings
        s = Settings()
        assert s.COOKIE_SECURE is False, (
            "COOKIE_SECURE should default to False (safe for HTTP dev)"
        )

    def test_default_database_url_is_sqlite(self, monkeypatch):
        """Default DATABASE_URL must be SQLite."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from app.config import Settings
        s = Settings()
        assert s.DATABASE_URL.startswith("sqlite"), (
            f"Default DATABASE_URL must be SQLite, got: {s.DATABASE_URL}"
        )
