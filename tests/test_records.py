from uuid import uuid4
from collections.abc import Callable

from sqlalchemy import func, select
from fastapi.testclient import TestClient

from td_plugin_api.db import Blob
from td_plugin_api.auth import caller

from tests.helpers import RUN, RULING, rule, changes, new_run

Token = Callable[..., dict[str, str]]


def test_requests_without_a_valid_token_are_refused(client: TestClient) -> None:
    assert client.get("/v1/me").status_code == 401
    response = client.get("/v1/me", headers={"Authorization": "Bearer tdp_unknown"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_a_read_token_cannot_write(client: TestClient, token: Token) -> None:
    response = client.put(f"/v1/runs/{uuid4()}", json=RUN, headers=token(scopes="read"))
    assert response.status_code == 403


def test_me_names_the_tokens_user_scopes_and_machine(client: TestClient, token: Token) -> None:
    me = client.get("/v1/me", headers=token(machine="59a937828f3c")).json()
    assert me | {"display_name": ""} == {
        "user": "wei",
        "display_name": "",
        "role": "member",
        "scopes": ["read", "write"],
        "machine": "59a937828f3c",
    }


def test_a_run_takes_its_defaults_and_keeps_fields_the_server_does_not_know(
    client: TestClient, token: Token
) -> None:
    headers = token(machine="m1")
    run_id = new_run(client, headers, client_meta={"conversation_id": "c1"}, later={"x": 1})
    run = client.get(f"/v1/runs/{run_id}", headers=headers).json()
    assert (run["status"], run["visibility"], run["has_holding"]) == ("running", "public", False)
    assert (run["language"], run["machine"], run["user"]) == ("Traditional Chinese", "m1", "wei")
    assert (run["client_meta"], run["later"]) == ({"conversation_id": "c1"}, {"x": 1})


def test_sending_the_same_body_again_records_no_change(client: TestClient, token: Token) -> None:
    headers = token()
    run_id = str(uuid4())
    for _ in range(2):
        assert client.put(f"/v1/runs/{run_id}", json=RUN, headers=headers).status_code == 200
    assert changes(client, headers) == [("run", "put")]


def test_a_ruling_cannot_change_and_marks_its_run_ruled(client: TestClient, token: Token) -> None:
    headers = token()
    run_id = new_run(client, headers)
    rule(client, headers, run_id)
    rule(client, headers, run_id)
    conflict = client.put(
        f"/v1/runs/{run_id}/ruling", json=RULING | {"direction": "bearish"}, headers=headers
    )
    assert conflict.status_code == 409
    # The run's first body sent again, as a client catching up would, keeps the ruled status.
    client.put(f"/v1/runs/{run_id}", json=RUN, headers=headers)
    run = client.get(f"/v1/runs/{run_id}", headers=headers).json()
    assert run["status"] == "ruled"
    assert run["ruling"] == RULING


def test_an_update_changes_only_the_fields_it_sends(client: TestClient, token: Token) -> None:
    headers = token()
    kept = {"host": "claude-code", "client_meta": {"conversation_id": "c1"}, "later": 1}
    run_id = new_run(client, headers, visibility="private", **kept)
    update = {"ticker": "NVDA", "finished_at": "2026-11-05T08:00:00+08:00"}
    run = client.put(f"/v1/runs/{run_id}", json=update, headers=headers).json()
    assert (run["visibility"], run["finished_at"]) == ("private", "2026-11-05T00:00:00Z")
    assert {key: run[key] for key in kept} == kept
    assert client.put(f"/v1/runs/{run_id}", json=update, headers=headers).status_code == 200
    assert changes(client, headers) == [("run", "put"), ("run", "put")]


def test_an_earlier_body_naming_its_status_cannot_undo_a_ruling(
    client: TestClient, token: Token
) -> None:
    headers = token()
    run_id = new_run(client, headers, status="running")
    rule(client, headers, run_id)
    client.put(f"/v1/runs/{run_id}", json=RUN | {"status": "ruled"}, headers=headers)
    client.put(f"/v1/runs/{run_id}", json=RUN | {"status": "running"}, headers=headers)
    assert client.get(f"/v1/runs/{run_id}", headers=headers).json()["status"] == "ruled"


def test_resolving_a_token_leaves_no_transaction_open(client: TestClient, token: Token) -> None:
    headers = token()
    with client.app.state.sessions() as session:
        assert caller(session, headers["Authorization"]).user.handle == "wei"
        assert not session.in_transaction()


def test_only_public_runs_without_a_holding_reach_other_users(
    client: TestClient, token: Token
) -> None:
    wei, amy = token("wei"), token("amy")
    public = new_run(client, wei)
    private = new_run(client, wei, visibility="private")
    holding = new_run(client, wei, has_holding=True)
    assert [
        client.get(f"/v1/runs/{r}", headers=amy).status_code for r in (public, private, holding)
    ] == [200, 404, 404]
    assert client.put(f"/v1/runs/{public}/ruling", json=RULING, headers=amy).status_code == 403
    assert client.put(f"/v1/runs/{private}/ruling", json=RULING, headers=amy).status_code == 404
    assert client.put(f"/v1/runs/{public}", json=RUN, headers=amy).status_code == 403
    assert [r["id"] for r in client.get("/v1/runs", headers=amy).json()["items"]] == [public]
    assert len(client.get("/v1/runs", headers=wei).json()["items"]) == 3


def test_a_deleted_run_disappears_but_its_delete_reaches_other_readers(
    client: TestClient, token: Token
) -> None:
    wei, amy = token("wei"), token("amy")
    run_id = new_run(client, wei)
    assert client.delete(f"/v1/runs/{run_id}", headers=wei).status_code == 204
    assert client.get(f"/v1/runs/{run_id}", headers=wei).status_code == 404
    assert client.put(f"/v1/runs/{run_id}", json=RUN | {"x": 1}, headers=wei).status_code == 404
    assert changes(client, wei) == [("run", "put"), ("run", "delete")]
    assert changes(client, amy) == [("run", "delete")]


def test_artifacts_round_trip_and_share_one_stored_body(client: TestClient, token: Token) -> None:
    headers = token()
    first, second = new_run(client, headers), new_run(client, headers)
    for run_id in (first, second):
        response = client.put(
            f"/v1/runs/{run_id}/artifacts/reports/market-analyst.md",
            content="# Market\n",
            params={"role": "market-analyst", "model": "model-a"},
            headers=headers | {"Content-Type": "text/markdown"},
        )
        assert response.status_code == 200
    got = client.get(f"/v1/runs/{first}/artifacts/reports/market-analyst.md", headers=headers)
    assert (got.text, got.headers["content-type"]) == (
        "# Market\n",
        "text/markdown; charset=utf-8",
    )
    listed = client.get(f"/v1/runs/{first}/artifacts", headers=headers).json()["items"]
    assert [(a["path"], a["role"], a["size"]) for a in listed] == [
        ("reports/market-analyst.md", "market-analyst", 9)
    ]
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Blob)) == 1
    bad = client.put(f"/v1/runs/{first}/artifacts/reports//x.md", content="x", headers=headers)
    assert bad.status_code == 422
    missing = client.get(f"/v1/runs/{first}/artifacts/none.md", headers=headers)
    assert missing.status_code == 404


def test_a_tool_call_keeps_its_output_apart(client: TestClient, token: Token) -> None:
    headers = token()
    run_id = new_run(client, headers)
    call = {
        "at": "2026-11-05T07:00:00Z",
        "role": "market-analyst",
        "tool": "get_stock_data",
        "params": {"symbol": "NVDA"},
        "output": "Date,Close\n2026-11-04,190.1\n",
    }
    for _ in range(2):
        assert (
            client.put(f"/v1/runs/{run_id}/calls/1", json=call, headers=headers).status_code == 200
        )
    listed = client.get(f"/v1/runs/{run_id}/calls", headers=headers).json()["items"]
    assert listed == [{k: v for k, v in call.items() if k != "output"} | {"n": 1}]
    output = client.get(f"/v1/runs/{run_id}/calls/1/output", headers=headers)
    assert output.text == call["output"]
    assert client.get(f"/v1/runs/{run_id}/calls/2/output", headers=headers).status_code == 404
    assert changes(client, headers, types="call") == [("call", "put")]


def test_the_records_under_a_run_come_back_with_it(client: TestClient, token: Token) -> None:
    headers = token()
    run_id = new_run(client, headers)
    base = f"/v1/runs/{run_id}"
    followup = {"at": "2026-11-06T22:00:00Z", "verdict": "holding", "note": "Still on course."}
    standing = {"method": "first-close", "return_pct": 1.2, "direction_hit": False}
    settlement = {"settled_at": "2026-11-28T00:00:00Z", "direction_hit": True}
    reflection = {"at": "2026-11-28T01:00:00Z", "text": "The bear was right about margins."}
    followup_id, reflection_id = uuid4(), uuid4()
    assert (
        client.put(f"{base}/followups/{followup_id}", json=followup, headers=headers).status_code
        == 200
    )
    assert (
        client.put(f"{base}/standings/2026-11-06", json=standing, headers=headers).status_code
        == 200
    )
    assert client.put(f"{base}/settlement", json=settlement, headers=headers).status_code == 200
    assert client.put(f"{base}/settlement", json=settlement, headers=headers).status_code == 200
    changed = settlement | {"direction_hit": False}
    assert client.put(f"{base}/settlement", json=changed, headers=headers).status_code == 409
    assert (
        client.put(
            f"{base}/reflections/{reflection_id}", json=reflection, headers=headers
        ).status_code
        == 200
    )
    other = new_run(client, headers)
    moved = client.put(f"/v1/runs/{other}/followups/{followup_id}", json=followup, headers=headers)
    assert moved.status_code == 409
    run = client.get(base, headers=headers).json()
    assert run["followups"] == [followup | {"id": str(followup_id)}]
    assert run["standings"] == [standing | {"as_of": "2026-11-06"}]
    assert run["settlement"] == settlement
    assert run["reflections"] == [reflection | {"id": str(reflection_id)}]
    assert client.get(f"{base}/followups", headers=headers).json()["items"] == run["followups"]
    assert client.get(f"{base}/standings", headers=headers).json()["items"] == run["standings"]


def test_a_machine_heartbeat_is_news_only_when_its_body_changes(
    client: TestClient, token: Token
) -> None:
    wei = token()
    body = {"host": "Wei", "settings": {"language": "Traditional Chinese"}}
    for sent in (body, body, body | {"status": {"lastRound": "2026-11-06"}}):
        assert client.put("/v1/machines/59a937828f3c", json=sent, headers=wei).status_code == 200
    assert changes(client, wei) == [("machine", "put"), ("machine", "put")]
    machines = client.get("/v1/machines", headers=wei).json()["items"]
    assert [(m["id"], m["status"]) for m in machines] == [
        ("59a937828f3c", {"lastRound": "2026-11-06"})
    ]
    assert (
        client.put("/v1/machines/59a937828f3c", json=body, headers=token("amy")).status_code == 403
    )


def test_the_watchlist_and_start_overs_stay_with_their_user(
    client: TestClient, token: Token
) -> None:
    wei, amy = token("wei"), token("amy")
    watch = {"watched": True, "follow": True, "holding": "120 shares at 172"}
    assert client.put("/v1/watchlist/2330.TW", json=watch, headers=wei).status_code == 200
    start_over = str(uuid4())
    assert (
        client.put(
            f"/v1/me/start-overs/{start_over}", json={"at": "2026-11-05T15:26:49Z"}, headers=wei
        ).status_code
        == 200
    )
    assert client.get("/v1/watchlist", headers=amy).json()["items"] == []
    assert client.get("/v1/me/start-overs", headers=amy).json()["items"] == []
    assert changes(client, amy) == []
    assert (
        client.put(
            f"/v1/me/start-overs/{start_over}", json={"at": "2026-11-05T15:26:49Z"}, headers=amy
        ).status_code
        == 403
    )
    listed = client.get("/v1/watchlist", headers=wei).json()["items"]
    assert [(w["ticker"], w["holding"]) for w in listed] == [("2330.TW", "120 shares at 172")]
    assert client.get("/v1/me/start-overs", headers=wei).json()["items"][0]["id"] == start_over
    assert client.delete("/v1/watchlist/2330.TW", headers=wei).status_code == 204
    assert client.delete("/v1/watchlist/2330.TW", headers=wei).status_code == 404


def test_a_job_is_seen_by_whoever_may_read_its_run(client: TestClient, token: Token) -> None:
    wei, amy = token("wei", machine="m1"), token("amy")
    public, private = new_run(client, wei), new_run(client, wei, visibility="private")
    jobs = {}
    for name, run in (("public", public), ("private", private), ("no_run", None)):
        jobs[name] = str(uuid4())
        body = {
            "kind": "analysis",
            "status": "running",
            "ticker": "NVDA",
            "run": run,
            "stage": "debate",
        }
        assert client.put(f"/v1/jobs/{jobs[name]}", json=body, headers=wei).status_code == 200
    assert [j["id"] for j in client.get("/v1/jobs", headers=amy).json()["items"]] == [
        jobs["public"]
    ]
    assert client.get(f"/v1/jobs/{jobs['no_run']}", headers=amy).status_code == 404
    mine = client.get(
        "/v1/jobs", params={"status": "running", "machine": "m1"}, headers=wei
    ).json()
    assert len(mine["items"]) == 3
    done = {"kind": "analysis", "status": "done", "run": public}
    assert client.put(f"/v1/jobs/{jobs['public']}", json=done, headers=amy).status_code == 403
    assert (
        client.put(f"/v1/jobs/{jobs['public']}", json=done, headers=wei).json()["status"] == "done"
    )
    assert client.get("/v1/jobs", params={"status": "running"}, headers=amy).json()["items"] == []


def test_lists_page_newest_first(client: TestClient, token: Token) -> None:
    headers = token()
    runs = [new_run(client, headers, created_at=f"2026-11-0{day}T00:00:00Z") for day in (1, 2, 3)]
    first = client.get("/v1/runs", params={"limit": 2}, headers=headers).json()
    assert [r["id"] for r in first["items"]] == runs[:0:-1]
    second = client.get(
        "/v1/runs", params={"limit": 2, "cursor": first["next_cursor"]}, headers=headers
    ).json()
    assert ([r["id"] for r in second["items"]], second["next_cursor"]) == ([runs[0]], None)
    bad = client.get("/v1/runs", params={"cursor": "nope"}, headers=headers)
    assert bad.status_code == 422


def test_a_malformed_body_gets_the_error_shape(client: TestClient, token: Token) -> None:
    response = client.put(
        f"/v1/runs/{uuid4()}", json=RUN | {"created_at": "2026-11-05T07:30:00"}, headers=token()
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid"
    assert client.get("/v1/nothing-here", headers=token()).json()["error"]["code"] == "error"
