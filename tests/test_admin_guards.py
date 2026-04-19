import pytest
from fastapi import HTTPException

from app.routes.admin import (
    _require_generic_admin_data_enabled,
    _require_generic_admin_data_write_enabled,
)
from app.routes.schema import (
    is_read_only_sql,
    require_admin_sql_enabled,
    require_admin_sql_write_enabled,
)


def test_admin_sql_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_ADMIN_SQL", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        require_admin_sql_enabled()

    assert exc_info.value.status_code == 403


def test_generic_admin_data_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_GENERIC_DATA_ADMIN", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        _require_generic_admin_data_enabled()

    assert exc_info.value.status_code == 403


def test_admin_sql_writes_are_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("ENABLE_ADMIN_SQL", "true")
    monkeypatch.delenv("ENABLE_ADMIN_SQL_WRITES", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        require_admin_sql_write_enabled()

    assert exc_info.value.status_code == 403


def test_generic_admin_data_writes_are_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("ENABLE_GENERIC_DATA_ADMIN", "true")
    monkeypatch.delenv("ENABLE_GENERIC_DATA_ADMIN_WRITES", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        _require_generic_admin_data_write_enabled()

    assert exc_info.value.status_code == 403


def test_is_read_only_sql_only_allows_safe_admin_queries():
    assert is_read_only_sql("SELECT * FROM entries")
    assert is_read_only_sql("  -- comment\nEXPLAIN SELECT * FROM entries")
    assert not is_read_only_sql("WITH x AS (DELETE FROM entries RETURNING *) SELECT * FROM x")
    assert not is_read_only_sql("DELETE FROM entries")
