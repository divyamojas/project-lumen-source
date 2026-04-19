"""Tests for DELETE /users/me and DELETE /users/me/entries endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


def _make_app():
    import os
    os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret")
    os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-pub")

    from app.main import app
    return app


@pytest.fixture
def mock_supabase():
    entries_delete = MagicMock()
    entries_delete.eq.return_value = entries_delete
    entries_delete.execute = AsyncMock(return_value=MagicMock(data=[{"id": "e1"}, {"id": "e2"}]))

    table_mock = MagicMock()
    table_mock.delete.return_value = entries_delete

    auth_admin = MagicMock()
    auth_admin.delete_user = AsyncMock(return_value=None)

    supabase = MagicMock()
    supabase.table.return_value = table_mock
    supabase.auth.admin = auth_admin
    return supabase


@pytest.fixture
def client(mock_supabase):
    app = _make_app()

    async def _fake_supabase():
        return mock_supabase

    async def _fake_user():
        return "user-123"

    from app.dependencies import get_supabase
    from app.auth import get_current_user

    app.dependency_overrides[get_supabase] = _fake_supabase
    app.dependency_overrides[get_current_user] = _fake_user

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ── DELETE /users/me ──────────────────────────────────────────────────────────

class TestDeleteAccount:
    def test_happy_path(self, client):
        resp = client.request(
            "DELETE", "/users/me", json={"confirm": "DELETE MY ACCOUNT"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted"] is True
        assert body["entries_removed"] == 2

    def test_wrong_confirmation_string(self, client):
        resp = client.request(
            "DELETE", "/users/me", json={"confirm": "delete my account"}
        )
        assert resp.status_code == 400

    def test_missing_confirmation_string(self, client):
        resp = client.request("DELETE", "/users/me", json={})
        assert resp.status_code == 400

    def test_unauthenticated(self):
        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.request("DELETE", "/users/me", json={"confirm": "DELETE MY ACCOUNT"})
        assert resp.status_code == 401 or resp.status_code == 403


# ── DELETE /users/me/entries ──────────────────────────────────────────────────

class TestDeleteMyEntries:
    def test_happy_path(self, client):
        resp = client.delete("/users/me/entries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted"] is True
        assert body["entries_removed"] == 2

    def test_unauthenticated(self):
        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.delete("/users/me/entries")
        assert resp.status_code == 401 or resp.status_code == 403
