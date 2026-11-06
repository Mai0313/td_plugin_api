import pytest
import uvicorn

from td_plugin_api.app import app
from td_plugin_api.cli import main


def test_main_serves_the_app_on_the_address_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setenv("TD_PLUGIN_API_HOST", "127.0.0.2")
    monkeypatch.setenv("TD_PLUGIN_API_PORT", "9123")
    main()
    assert calls == [((app,), {"host": "127.0.0.2", "port": 9123})]
