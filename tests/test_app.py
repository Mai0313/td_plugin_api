from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from alembic.autogenerate import compare_metadata

from td_plugin_api.db import Base
from td_plugin_api.app import app


def test_healthz_reports_ok() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_migrations_build_the_tables_the_models_describe(client: TestClient) -> None:
    with client.app.state.sessions() as session:
        context = MigrationContext.configure(session.connection())
        assert compare_metadata(context, Base.metadata) == []
