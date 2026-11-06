import json
from uuid import uuid4
from collections.abc import Callable

import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient

from td_plugin_api import reads
from td_plugin_api.db import User

from tests.helpers import rule, changes, new_run

Token = Callable[..., dict[str, str]]

SUMMARY = {
    "what_to_do": "Wait for a close above 190.",
    "key_points": [{"question": "Do margins hold?", "ruling": "Yes, for now."}],
    "invalidation": [{"condition": "A close below 175", "kind": "close_below", "value": 175}],
}


def test_a_call_puts_the_ruling_together_with_what_belongs_to_it(
    client: TestClient, token: Token
) -> None:
    headers = token()
    run_id = new_run(client, headers)
    rule(client, headers, run_id)
    base = f"/v1/runs/{run_id}"
    client.put(f"{base}/artifacts/summary.json", content=json.dumps(SUMMARY), headers=headers)
    client.put(f"{base}/artifacts/decision.md", content="# Decision\n", headers=headers)
    followup = {
        "at": "2026-11-06T22:00:00Z",
        "verdict": "holding",
        "note": "On course.",
        "body": "Long text.",
    }
    client.put(f"{base}/followups/{uuid4()}", json=followup, headers=headers)
    client.put(f"{base}/standings/2026-11-05", json={"return_pct": 0.1}, headers=headers)
    client.put(f"{base}/standings/2026-11-06", json={"return_pct": 1.2}, headers=headers)

    call = client.get(
        f"/v1/calls/{run_id}", params={"include": "key_points,followups"}, headers=headers
    ).json()
    assert (call["status"], call["direction"], call["model"], call["user"]) == (
        "open",
        "bullish",
        "model-a",
        "wei",
    )
    assert call["target"] == {"low": 180.0, "likely": 195.0, "high": 210.0}
    assert (call["wrong_below"], call["what_to_do"]) == (175.0, SUMMARY["what_to_do"])
    assert call["latest_followup"] == {
        "at": "2026-11-06T22:00:00Z",
        "verdict": "holding",
        "note": "On course.",
    }
    assert call["latest_standing"] == {"return_pct": 1.2, "as_of": "2026-11-06"}
    assert call["links"] == {"run": base, "decision": f"{base}/artifacts/decision.md"}
    assert call["key_points"] == SUMMARY["key_points"]
    assert "invalidation" not in call
    assert call["followups"][0]["body"] == "Long text."
    assert (
        client.get(f"/v1/calls/{run_id}", params={"include": "nope"}, headers=headers).status_code
        == 422
    )

    client.put(f"{base}/settlement", json={"settled_at": "2026-11-28T00:00:00Z"}, headers=headers)
    settled = client.get("/v1/calls", params={"status": "settled"}, headers=headers).json()[
        "items"
    ]
    assert [(c["id"], c["status"]) for c in settled] == [(run_id, "settled")]
    assert (
        client.get("/v1/calls", params={"status": "open"}, headers=headers).json()["items"] == []
    )


def test_a_run_without_a_ruling_is_not_a_call(client: TestClient, token: Token) -> None:
    headers = token()
    run_id = new_run(client, headers)
    assert client.get(f"/v1/calls/{run_id}", headers=headers).status_code == 404
    assert client.get("/v1/calls", headers=headers).json()["items"] == []


def test_a_start_over_hides_its_users_earlier_calls_unless_all(
    client: TestClient, token: Token
) -> None:
    wei, amy = token("wei"), token("amy")
    old, new = new_run(client, wei), new_run(client, wei)
    rule(client, wei, old, ruled_at="2026-11-01T00:00:00Z")
    rule(client, wei, new, ruled_at="2026-11-05T00:00:00Z")
    client.put(f"/v1/me/start-overs/{uuid4()}", json={"at": "2026-11-03T00:00:00Z"}, headers=wei)
    client.put(f"/v1/me/start-overs/{uuid4()}", json={"at": "2026-11-09T00:00:00Z"}, headers=amy)

    def ids(**params: str) -> list[str]:
        return [
            c["id"] for c in client.get("/v1/calls", params=params, headers=amy).json()["items"]
        ]

    assert ids() == [new]
    assert ids(all="true") == [new, old]
    assert ids(since="2026-11-04T00:00:00Z", all="true") == [new]
    assert ids(user="wei") == [new]
    assert ids(user="amy") == []


def test_latest_keeps_the_newest_call_on_a_ticker(client: TestClient, token: Token) -> None:
    headers = token()
    first, second = new_run(client, headers), new_run(client, headers)
    rule(client, headers, first, ruled_at="2026-11-01T00:00:00Z", model="model-a")
    rule(client, headers, second, ruled_at="2026-11-02T00:00:00Z", model="model-b")

    def latest(**params: str) -> list[str]:
        found = client.get(
            "/v1/tickers/NVDA/calls", params={"latest": "true"} | params, headers=headers
        ).json()
        assert found["next_cursor"] is None
        return [c["id"] for c in found["items"]]

    assert latest() == [second]
    assert latest(model="model-a") == [first]
    every = client.get("/v1/tickers/NVDA/calls", params={"limit": 1}, headers=headers).json()
    assert every["next_cursor"] is not None
    assert client.get("/v1/tickers/AAPL/calls", headers=headers).json()["items"] == []


def test_changes_show_a_reader_only_what_they_may_read(client: TestClient, token: Token) -> None:
    wei, amy = token("wei"), token("amy")
    public = new_run(client, wei)
    new_run(client, wei, visibility="private")
    client.put("/v1/watchlist/NVDA", json={}, headers=wei)
    rule(client, wei, public)
    assert changes(client, amy) == [("run", "put"), ("ruling", "put")]
    assert changes(client, wei, types="watchlist,ruling") == [
        ("watchlist", "put"),
        ("ruling", "put"),
    ]
    page = client.get("/v1/changes", params={"limit": 2}, headers=wei).json()
    rest = client.get("/v1/changes", params={"after": page["next_cursor"]}, headers=wei).json()
    assert len(page["items"]) + len(rest["items"]) == 4


async def test_the_event_stream_sends_changes_then_keepalives_until_the_client_leaves(
    client: TestClient, token: Token, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = token()
    new_run(client, headers)
    monkeypatch.setattr(reads, "POLL_SECONDS", 0)
    monkeypatch.setattr(reads, "KEEPALIVE_SECONDS", 0)

    class Leaves:
        polls = 0

        async def is_disconnected(self) -> bool:
            self.polls += 1
            return self.polls > 2

    sessions = client.app.state.sessions
    with sessions() as session:
        user_id = session.scalar(select(User.id).where(User.handle == "wei"))
    chunks = [chunk async for chunk in reads.event_stream(Leaves(), sessions, user_id, 0, set())]
    assert chunks[0].startswith("id: 1\nevent: run\ndata: ")
    assert json.loads(chunks[0].split("data: ")[1])["op"] == "put"
    assert chunks[1:] == [": keepalive\n\n"]


def test_the_event_stream_refuses_a_malformed_last_event_id(
    client: TestClient, token: Token
) -> None:
    response = client.get("/v1/events", headers=token() | {"Last-Event-ID": "x"})
    assert response.status_code == 422
