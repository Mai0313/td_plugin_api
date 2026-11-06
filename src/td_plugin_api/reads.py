"""What readers ask for: calls put together from the record, and the feed of changes."""

import json
import time
from uuid import UUID
from typing import Any, Protocol, Annotated
import asyncio
from collections.abc import AsyncIterator

from fastapi import Query, Header, Request, APIRouter
from sqlalchemy import or_, and_, func, exists, select
from sqlalchemy.orm import Session, sessionmaker
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from td_plugin_api.db import (
    Run,
    Blob,
    User,
    Change,
    Ruling,
    Artifact,
    Followup,
    Standing,
    StartOver,
    Settlement,
    parse_time,
    format_time,
)
from td_plugin_api.auth import Reader, SessionDep, fail, readable
from td_plugin_api.records import page, handle, standing_out
from td_plugin_api.schemas import CallQuery

router = APIRouter(prefix="/v1")

POLL_SECONDS = 1.0
KEEPALIVE_SECONDS = 30.0
INCLUDES = {"key_points", "invalidation", "followups", "standings"}


def _summary(session: Session, run_id: str) -> dict[str, Any]:
    row = session.get(Artifact, (run_id, "summary.json"))
    if row is None:
        return {}
    try:
        summary = json.loads(session.get_one(Blob, row.sha256).data)
    except ValueError:
        return {}
    return summary if isinstance(summary, dict) else {}


def card(session: Session, run: Run, ruling: Ruling, include: set[str]) -> dict[str, Any]:
    """One call: the ruling with what belongs to it, as stored."""
    summary = _summary(session, run.id)
    followups = list(
        session.scalars(select(Followup).where(Followup.run_id == run.id).order_by(Followup.at))
    )
    standings = list(
        session.scalars(select(Standing).where(Standing.run_id == run.id).order_by(Standing.as_of))
    )
    settlement = session.get(Settlement, run.id)
    paths = set(session.scalars(select(Artifact.path).where(Artifact.run_id == run.id)))
    links = {"run": f"/v1/runs/{run.id}"}
    for name in ("decision.md", "debate.md"):
        if name in paths:
            links[name.removesuffix(".md")] = f"/v1/runs/{run.id}/artifacts/{name}"
    latest = followups[-1].payload if followups else None
    out: dict[str, Any] = {
        "id": run.id,
        "slug": run.slug,
        "ticker": run.ticker,
        "benchmark": run.benchmark,
        "user": handle(session, run.user_id),
        "model": ruling.model or run.model,
        "language": run.language,
        "ruled_at": format_time(ruling.ruled_at),
        "check_date": ruling.check_date,
        "status": "settled" if settlement else "open",
        "direction": ruling.direction,
        "probability": ruling.probability,
        "confidence": ruling.confidence,
        "action": ruling.action,
        "target": {
            "low": ruling.target_low,
            "likely": ruling.target_likely,
            "high": ruling.target_high,
        },
        "wrong_below": ruling.payload.get("wrong_below"),
        "wrong_above": ruling.payload.get("wrong_above"),
        "what_to_do": summary.get("what_to_do"),
        "latest_followup": {key: latest.get(key) for key in ("at", "verdict", "note")}
        if latest
        else None,
        "latest_standing": standing_out(standings[-1]) if standings else None,
        "settlement": settlement.payload if settlement else None,
        "links": links,
    }
    for key in ("key_points", "invalidation"):
        if key in include:
            out[key] = summary.get(key)
    if "followups" in include:
        out["followups"] = [row.payload | {"id": row.id} for row in followups]
    if "standings" in include:
        out["standings"] = [standing_out(row) for row in standings]
    return out


def _includes(include: str | None) -> set[str]:
    wanted = set(filter(None, (include or "").split(",")))
    if not wanted <= INCLUDES:
        raise fail(422, "invalid", f"include takes {', '.join(sorted(INCLUDES))}.")
    return wanted


def _calls(session: Session, user_id: int, wanted: CallQuery) -> dict[str, Any]:
    include = _includes(wanted.include)
    query = select(Run, Ruling).join(Ruling, Ruling.run_id == Run.id).where(readable(user_id))
    if not wanted.all_:
        # A user's start-over hides the calls they ruled before it; nothing is deleted.
        latest = (
            select(StartOver.user_id, func.max(StartOver.at).label("at"))
            .group_by(StartOver.user_id)
            .subquery()
        )
        query = query.outerjoin(latest, latest.c.user_id == Run.user_id).where(
            or_(latest.c.at.is_(None), Ruling.ruled_at > latest.c.at)
        )
    if wanted.ticker:
        query = query.where(Run.ticker == wanted.ticker)
    if wanted.user:
        query = query.join(User, User.id == Run.user_id).where(User.handle == wanted.user)
    if wanted.model:
        query = query.where(Ruling.model == wanted.model)
    if wanted.status:
        settled = exists().where(Settlement.run_id == Run.id)
        query = query.where(settled if wanted.status == "settled" else ~settled)
    if wanted.since:
        query = query.where(Ruling.ruled_at >= parse_time(wanted.since))
    rows, next_cursor = page(session, query, Ruling.ruled_at, Run.id, wanted)
    return {
        "items": [card(session, row[0], row[1], include) for row in rows],
        "next_cursor": next_cursor,
    }


@router.get("/calls")
def list_calls(
    who: Reader, session: SessionDep, wanted: Annotated[CallQuery, Query()]
) -> dict[str, Any]:
    """Calls newest first; `all=true` keeps the calls a user's start-over hides."""
    return _calls(session, who.user.id, wanted)


@router.get("/calls/{call_id}")
def get_call(
    call_id: UUID, who: Reader, session: SessionDep, include: str | None = None
) -> dict[str, Any]:
    row = session.execute(
        select(Run, Ruling)
        .join(Ruling, Ruling.run_id == Run.id)
        .where(Run.id == str(call_id), readable(who.user.id))
    ).first()
    if row is None:
        raise fail(404, "not_found", "No such call.")
    return card(session, row[0], row[1], _includes(include))


@router.get("/tickers/{symbol}/calls")
def ticker_calls(
    symbol: str,
    who: Reader,
    session: SessionDep,
    wanted: Annotated[CallQuery, Query()],
    latest: bool = False,
) -> dict[str, Any]:
    """A ticker's calls newest first; `latest=true` keeps only the newest (of `model`, when given)."""
    update: dict[str, Any] = {"ticker": symbol}
    if latest:
        update |= {"limit": 1, "cursor": None}
    found = _calls(session, who.user.id, wanted.model_copy(update=update))
    if latest:
        found["next_cursor"] = None
    return found


# ------------------------------------------------------------------- changes


def read_changes(
    session: Session, user_id: int, after: int, kinds: set[str], limit: int
) -> list[dict[str, Any]]:
    """Changes after `after` that the user may see: their own, and those of runs they may read.

    Of a deleted run, others still see the delete, so a reader that copied the run drops it.
    """
    query = (
        select(Change)
        .outerjoin(Run, Run.id == Change.run_id)
        .where(
            Change.seq > after,
            or_(
                Change.user_id == user_id,
                and_(
                    Run.visibility == "public",
                    Run.has_holding.is_(False),
                    or_(
                        Run.deleted_at.is_(None), and_(Change.kind == "run", Change.op == "delete")
                    ),
                ),
            ),
        )
    )
    if kinds:
        query = query.where(Change.kind.in_(kinds))
    rows = session.scalars(query.order_by(Change.seq).limit(limit))
    return [
        {
            "seq": row.seq,
            "at": format_time(row.at),
            "kind": row.kind,
            "run": row.run_id,
            "ref": row.ref,
            "op": row.op,
        }
        for row in rows
    ]


def _kinds(types: str | None) -> set[str]:
    return set(filter(None, (types or "").split(",")))


@router.get("/changes")
def list_changes(
    who: Reader,
    session: SessionDep,
    after: int = 0,
    types: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> dict[str, Any]:
    """Changes after the number `after`, oldest first; pass the returned `next_cursor` as the next `after`."""
    items = read_changes(session, who.user.id, after, _kinds(types), limit)
    return {"items": items, "next_cursor": str(items[-1]["seq"]) if len(items) == limit else None}


def _poll(
    sessions: sessionmaker[Session], user_id: int, after: int, kinds: set[str]
) -> list[dict[str, Any]]:
    with sessions() as session:
        return read_changes(session, user_id, after, kinds, 500)


def _last_seq(sessions: sessionmaker[Session]) -> int:
    with sessions() as session:
        return session.scalar(select(func.max(Change.seq))) or 0


class Connection(Protocol):
    async def is_disconnected(self) -> bool: ...


async def event_stream(
    request: Connection, sessions: sessionmaker[Session], user_id: int, after: int, kinds: set[str]
) -> AsyncIterator[str]:
    """Server-sent events for each visible change after `after`, until the client goes away."""
    quiet_since = time.monotonic()
    while not await request.is_disconnected():
        items = await run_in_threadpool(_poll, sessions, user_id, after, kinds)
        for item in items:
            yield f"id: {item['seq']}\nevent: {item['kind']}\ndata: {json.dumps(item)}\n\n"
            after = item["seq"]
        if items:
            quiet_since = time.monotonic()
        elif time.monotonic() - quiet_since >= KEEPALIVE_SECONDS:
            # A comment line, so proxies do not close a quiet connection.
            yield ": keepalive\n\n"
            quiet_since = time.monotonic()
        await asyncio.sleep(POLL_SECONDS)


@router.get("/events")
async def events(
    request: Request,
    who: Reader,
    after: int | None = None,
    types: str | None = None,
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Changes as server-sent events, from `Last-Event-ID` or `after`, or from now when neither is sent."""
    sessions = request.app.state.sessions
    if last_event_id is not None:
        if not last_event_id.isdigit():
            raise fail(422, "invalid", "Last-Event-ID is the number of the last event received.")
        after = int(last_event_id)
    elif after is None:
        after = await run_in_threadpool(_last_seq, sessions)
    return StreamingResponse(
        event_stream(request, sessions, who.user.id, after, _kinds(types)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
