from uuid import uuid4

from fastapi.testclient import TestClient

RUN = {"ticker": "NVDA", "benchmark": "SPY", "slug": "NVDA_2026-11-05_151145", "model": "model-a"}
RULING = {
    "type": "ruling",
    "ruled_at": "2026-11-05T07:30:00+00:00",
    "direction": "bullish",
    "probability": 0.6,
    "target_low": 180.0,
    "target_likely": 195.0,
    "target_high": 210.0,
    "check_date": "2026-11-27",
    "wrong_below": 175.0,
    "model": "model-a",
    "a_field_added_later": {"kept": True},
}


def new_run(client: TestClient, headers: dict[str, str], **fields: object) -> str:
    run_id = str(uuid4())
    response = client.put(f"/v1/runs/{run_id}", json=RUN | fields, headers=headers)
    assert response.status_code == 200, response.text
    return run_id


def rule(client: TestClient, headers: dict[str, str], run_id: str, **fields: object) -> None:
    response = client.put(f"/v1/runs/{run_id}/ruling", json=RULING | fields, headers=headers)
    assert response.status_code == 200, response.text


def changes(
    client: TestClient, headers: dict[str, str], **params: object
) -> list[tuple[str, str]]:
    items = client.get("/v1/changes", params=params, headers=headers).json()["items"]
    return [(item["kind"], item["op"]) for item in items]
