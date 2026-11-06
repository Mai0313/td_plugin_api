import pytest
import uvicorn
from fastapi.testclient import TestClient

from td_plugin_api.app import app
from td_plugin_api.cli import main


def test_main_serves_the_app_on_the_address_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setenv("TD_PLUGIN_API_HOST", "127.0.0.2")
    monkeypatch.setenv("TD_PLUGIN_API_PORT", "9123")
    main([])
    assert calls == [((app,), {"host": "127.0.0.2", "port": 9123})]


def test_admin_makes_a_user_and_a_token_that_works_until_revoked(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["admin", "create-user", "wei", "--role", "owner"])
    main(["admin", "create-token", "wei", "--name", "desk", "--machine", "m1"])
    token_id, secret = capsys.readouterr().out.splitlines()[-1].removeprefix("token ").split(": ")
    headers = {"Authorization": f"Bearer {secret}"}
    me = client.get("/v1/me", headers=headers).json()
    assert (me["user"], me["role"], me["machine"]) == ("wei", "owner", "m1")
    main(["admin", "revoke-token", token_id])
    assert client.get("/v1/me", headers=headers).status_code == 401


@pytest.mark.parametrize(
    "argv", [["admin", "create-token", "nobody", "--name", "x"], ["admin", "revoke-token", "99"]]
)
def test_admin_exits_with_a_message_on_a_bad_request(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exited:
        main(argv)
    assert exited.value.code == 1
    assert capsys.readouterr().err


def test_admin_refuses_a_duplicate_user_and_an_unknown_scope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["admin", "create-user", "wei"])
    for argv in (
        ["admin", "create-user", "wei"],
        ["admin", "create-token", "wei", "--name", "x", "--scopes", "admin"],
    ):
        with pytest.raises(SystemExit):
            main(argv)
    assert "already exists" in capsys.readouterr().err
