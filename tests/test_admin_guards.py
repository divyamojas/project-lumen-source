import pytest
from fastapi import HTTPException

from app.routes.admin import _require_generic_admin_data_enabled
from app.routes.schema import require_admin_sql_enabled


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
