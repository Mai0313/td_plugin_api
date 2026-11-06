from pathlib import Path
from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient

from td_plugin_api.db import User
from td_plugin_api.app import app
from td_plugin_api.auth import create_user, create_token

Headers = dict[str, str]


@pytest.fixture(autouse=True)
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test gets its own database file, so none touches the real one under data/."""
    monkeypatch.setenv("TD_PLUGIN_API_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def token(client: TestClient) -> Callable[..., Headers]:
    """Headers carrying a new token for `handle`, made the way the admin command makes one."""

    def make(
        handle: str = "wei", scopes: str = "read,write", machine: str | None = None
    ) -> Headers:
        with client.app.state.sessions() as session:
            if session.scalar(select(User).where(User.handle == handle)) is None:
                create_user(session, handle)
            _, secret = create_token(session, handle, "test", scopes, machine)
        return {"Authorization": f"Bearer {secret}"}

    return make
