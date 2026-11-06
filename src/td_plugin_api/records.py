"""What clients write: machines, runs and everything under them, the watchlist, start-overs and jobs."""

import json
from uuid import UUID
import base64
from typing import Any, Annotated
import hashlib
from datetime import datetime
import mimetypes
from dataclasses import dataclass

from fastapi import Path, Query, Request, Response, APIRouter
from pydantic import BaseModel
from sqlalchemy import Row, Select, or_, and_, text, select
from sqlalchemy.orm import Session, InstrumentedAttribute, sessionmaker
from sqlalchemy.dialects import sqlite, postgresql
from starlette.concurrency import run_in_threadpool

from td_plugin_api.db import (
    Job,
    Run,
    Blob,
    Call,
    User,
    Watch,
    Change,
    Ruling,
    Machine,
    Artifact,
    Followup,
    Standing,
    StartOver,
    Reflection,
    Settlement,
    now,
    parse_time,
    format_time,
)
from td_plugin_api.auth import Caller, Reader, Writer, SessionDep, fail, readable
from td_plugin_api.schemas import (
    Day,
    JobIn,
    RunIn,
    Paging,
    WatchIn,
    JobQuery,
    RulingIn,
    RunQuery,
    MachineIn,
    FollowupIn,
    StandingIn,
    ToolCallIn,
    StartOverIn,
    ReflectionIn,
    SettlementIn,
)

router = APIRouter(prefix="/v1")

MachineId = Annotated[str, Path(pattern=r"^[\w.-]{1,64}$")]


def feed(session: Session, change: Change) -> None:
    """Add `change` to the feed; the caller commits right after."""
    if session.get_bind().dialect.name == "postgresql":
        # Held until commit, so feed numbers are handed out in commit order: a reader that has seen a number has seen every smaller one.
        session.execute(text("SELECT pg_advisory_xact_lock(7311)"))
    session.add(change)


def store_blob(session: Session, data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    # Two requests may store the same body at once; the second finds the row there and moves on.
    dialect = postgresql if session.get_bind().dialect.name == "postgresql" else sqlite
    session.execute(
        dialect
        .insert(Blob)
        .values(sha256=sha, size=len(data), data=data)
        .on_conflict_do_nothing(index_elements=[Blob.sha256])
    )
    return sha


def page(
    session: Session,
    query: Select[*tuple[Any, ...]],
    order: InstrumentedAttribute[datetime],
    key: InstrumentedAttribute[str],
    paging: Paging,
) -> tuple[list[Row[*tuple[Any, ...]]], str | None]:
    """One page of `query`, newest `order` first, after the row `paging.cursor` names; and the cursor of the next page."""
    if paging.cursor:
        try:
            stamp, last = json.loads(base64.urlsafe_b64decode(paging.cursor))
            stamp = datetime.fromisoformat(stamp)
        except ValueError as exc:
            raise fail(422, "invalid", "That cursor did not come from this API.") from exc
        query = query.where(or_(order < stamp, and_(order == stamp, key < last)))
    query = query.add_columns(order, key).order_by(order.desc(), key.desc())
    rows = list(session.execute(query.limit(paging.limit + 1)))
    if len(rows) <= paging.limit:
        return rows, None
    rows = rows[: paging.limit]
    stamp, last = rows[-1][-2], rows[-1][-1]
    return rows, base64.urlsafe_b64encode(json.dumps([stamp.isoformat(), last]).encode()).decode()


def handle(session: Session, user_id: int) -> str:
    return session.get_one(User, user_id).handle


def guard(run: Run, who: Caller) -> None:
    """Refuse a write to a run that is not the caller's: as missing when they cannot read it either."""
    if run.user_id == who.user.id:
        return
    if run.deleted_at is None and run.visibility == "public" and not run.has_holding:
        raise fail(403, "forbidden", "This run belongs to another user.")
    raise fail(404, "not_found", "No such run.")


def visible_run(session: Session, run_id: UUID, who: Caller) -> Run:
    run = session.scalar(select(Run).where(Run.id == str(run_id), readable(who.user.id)))
    if run is None:
        raise fail(404, "not_found", "No such run.")
    return run


def owned_run(session: Session, run_id: UUID, who: Caller) -> Run:
    run = session.get(Run, str(run_id))
    if run is None or run.deleted_at is not None:
        raise fail(404, "not_found", "No such run.")
    guard(run, who)
    return run


def run_out(session: Session, run: Run) -> dict[str, Any]:
    return run.payload | {
        "id": run.id,
        "user": handle(session, run.user_id),
        "machine": run.machine_id,
        "slug": run.slug,
        "ticker": run.ticker,
        "benchmark": run.benchmark,
        "status": run.status,
        "visibility": run.visibility,
        "has_holding": run.has_holding,
        "language": run.language,
        "model": run.model,
        "created_at": format_time(run.created_at),
        "finished_at": format_time(run.finished_at),
    }


def artifact_out(row: Artifact) -> dict[str, Any]:
    return {
        "path": row.path,
        "content_type": row.content_type,
        "sha256": row.sha256,
        "size": row.size,
        "role": row.role,
        "model": row.model,
        "updated_at": format_time(row.updated_at),
    }


def standing_out(row: Standing) -> dict[str, Any]:
    return row.payload | {"as_of": row.as_of}


def job_out(session: Session, row: Job) -> dict[str, Any]:
    return row.payload | {
        "id": row.id,
        "user": handle(session, row.user_id),
        "machine": row.machine_id,
        "run": row.run_id,
        "created_at": format_time(row.created_at),
        "updated_at": format_time(row.updated_at),
    }


@router.get("/me")
def me(who: Reader) -> dict[str, Any]:
    return {
        "user": who.user.handle,
        "display_name": who.user.display_name,
        "role": who.user.role,
        "scopes": sorted(who.scopes),
        "machine": who.machine_id,
    }


# ------------------------------------------------------------------ machines


def machine_out(row: Machine) -> dict[str, Any]:
    return row.payload | {"id": row.id, "seen_at": format_time(row.seen_at)}


@router.get("/machines")
def list_machines(who: Reader, session: SessionDep) -> dict[str, Any]:
    rows = session.scalars(
        select(Machine).where(Machine.user_id == who.user.id).order_by(Machine.id)
    )
    return {"items": [machine_out(row) for row in rows], "next_cursor": None}


@router.put("/machines/{machine_id}")
def put_machine(
    machine_id: MachineId, body: MachineIn, who: Writer, session: SessionDep
) -> dict[str, Any]:
    payload = body.payload()
    row = session.get(Machine, machine_id)
    if row is not None and row.user_id != who.user.id:
        raise fail(403, "forbidden", "This machine belongs to another user.")
    if row is None:
        row = Machine(id=machine_id, user_id=who.user.id, payload=payload, seen_at=now())
        session.add(row)
        feed(session, Change(user_id=who.user.id, kind="machine", ref=machine_id))
    elif row.payload != payload:
        row.payload = payload
        feed(session, Change(user_id=who.user.id, kind="machine", ref=machine_id))
    # Every write is a heartbeat, but only a changed body is news to other readers.
    row.seen_at = now()
    session.commit()
    return machine_out(row)


# ---------------------------------------------------------------------- runs


@router.put("/runs/{run_id}")
def put_run(run_id: UUID, body: RunIn, who: Writer, session: SessionDep) -> dict[str, Any]:
    payload = body.payload()
    run = session.get(Run, str(run_id))
    if run is not None:
        guard(run, who)
        if run.deleted_at is not None:
            raise fail(404, "not_found", "This run was deleted.")
        # A field left out of an update keeps its value.
        payload = run.payload | payload
        if run.payload == payload:
            return run_out(session, run)
        fields = body.model_fields_set
    else:
        created = parse_time(body.created_at) if body.created_at else now()
        run = Run(id=str(run_id), user_id=who.user.id, created_at=created)
        session.add(run)
        fields = set(RunIn.model_fields)
    for name in (
        "ticker",
        "benchmark",
        "slug",
        "status",
        "visibility",
        "has_holding",
        "language",
        "model",
    ):
        if name in fields:
            setattr(run, name, getattr(body, name))
    if "machine" in fields:
        run.machine_id = body.machine or who.machine_id
    if "finished_at" in fields:
        run.finished_at = parse_time(body.finished_at) if body.finished_at else None
    run.payload = payload
    if session.get(Ruling, run.id) is not None:
        # An earlier body sent again, as by a client catching up, cannot undo the ruling.
        run.status = "ruled"
    feed(session, Change(user_id=who.user.id, kind="run", ref=run.id, run_id=run.id))
    session.commit()
    return run_out(session, run)


@router.get("/runs")
def list_runs(
    who: Reader, session: SessionDep, wanted: Annotated[RunQuery, Query()]
) -> dict[str, Any]:
    query = select(Run).where(readable(who.user.id))
    if wanted.ticker:
        query = query.where(Run.ticker == wanted.ticker)
    if wanted.user:
        query = query.join(User, User.id == Run.user_id).where(User.handle == wanted.user)
    if wanted.model:
        query = query.where(Run.model == wanted.model)
    if wanted.status:
        query = query.where(Run.status == wanted.status)
    if wanted.since:
        query = query.where(Run.created_at >= parse_time(wanted.since))
    rows, next_cursor = page(session, query, Run.created_at, Run.id, wanted)
    return {"items": [run_out(session, row[0]) for row in rows], "next_cursor": next_cursor}


@router.get("/runs/{run_id}")
def get_run(run_id: UUID, who: Reader, session: SessionDep) -> dict[str, Any]:
    run = visible_run(session, run_id, who)
    ruling = session.get(Ruling, run.id)
    settlement = session.get(Settlement, run.id)
    artifacts = select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.path)
    calls = select(Call).where(Call.run_id == run.id).order_by(Call.n)
    followups = select(Followup).where(Followup.run_id == run.id).order_by(Followup.at)
    standings = select(Standing).where(Standing.run_id == run.id).order_by(Standing.as_of)
    reflections = select(Reflection).where(Reflection.run_id == run.id).order_by(Reflection.at)
    return run_out(session, run) | {
        "ruling": ruling.payload if ruling else None,
        "settlement": settlement.payload if settlement else None,
        "artifacts": [artifact_out(row) for row in session.scalars(artifacts)],
        "calls": [row.payload | {"n": row.n} for row in session.scalars(calls)],
        "followups": [row.payload | {"id": row.id} for row in session.scalars(followups)],
        "standings": [standing_out(row) for row in session.scalars(standings)],
        "reflections": [row.payload | {"id": row.id} for row in session.scalars(reflections)],
    }


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: UUID, who: Writer, session: SessionDep) -> Response:
    run = owned_run(session, run_id, who)
    run.deleted_at = now()
    feed(session, Change(user_id=who.user.id, kind="run", ref=run.id, run_id=run.id, op="delete"))
    session.commit()
    return Response(status_code=204)


# ----------------------------------------------------------------- artifacts


def _artifact_path(path: str) -> str:
    parts = path.split("/")
    if len(path) > 500 or any(part in ("", ".", "..") for part in parts):
        raise fail(
            422, "invalid", "An artifact path is relative, with no empty, `.` or `..` parts."
        )
    return path


@dataclass
class Upload:
    path: str
    data: bytes
    content_type: str
    role: str | None
    model: str | None


class ArtifactBy(BaseModel):
    """Who wrote an artifact, when known."""

    role: str | None = None
    model: str | None = None


def _put_artifact(
    sessions: sessionmaker[Session], who: Caller, run_id: UUID, upload: Upload
) -> dict[str, Any]:
    with sessions() as session:
        run = owned_run(session, run_id, who)
        sha = store_blob(session, upload.data)
        row = session.get(Artifact, (run.id, upload.path))
        stored = (sha, upload.content_type, upload.role, upload.model)
        if row is not None and (row.sha256, row.content_type, row.role, row.model) == stored:
            return artifact_out(row)
        if row is None:
            row = Artifact(run_id=run.id, path=upload.path)
            session.add(row)
        row.sha256, row.content_type, row.role, row.model = stored
        row.size, row.updated_at = len(upload.data), now()
        ref = f"{run.id}/{upload.path}"
        feed(session, Change(user_id=who.user.id, kind="artifact", ref=ref, run_id=run.id))
        session.commit()
        return artifact_out(row)


@router.put("/runs/{run_id}/artifacts/{path:path}")
async def put_artifact(
    run_id: UUID, path: str, request: Request, who: Writer, by: Annotated[ArtifactBy, Query()]
) -> dict[str, Any]:
    """Store a file the run wrote; the request body is the file, and `role` and `model` say who wrote it."""
    path = _artifact_path(path)
    content_type = (
        request.headers.get("content-type")
        or mimetypes.guess_type(path)[0]
        or "application/octet-stream"
    )
    upload = Upload(path, await request.body(), content_type, by.role, by.model)
    return await run_in_threadpool(_put_artifact, request.app.state.sessions, who, run_id, upload)


@router.get("/runs/{run_id}/artifacts")
def list_artifacts(run_id: UUID, who: Reader, session: SessionDep) -> dict[str, Any]:
    run = visible_run(session, run_id, who)
    rows = session.scalars(
        select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.path)
    )
    return {"items": [artifact_out(row) for row in rows], "next_cursor": None}


@router.get("/runs/{run_id}/artifacts/{path:path}")
def get_artifact(run_id: UUID, path: str, who: Reader, session: SessionDep) -> Response:
    run = visible_run(session, run_id, who)
    row = session.get(Artifact, (run.id, path))
    if row is None:
        raise fail(404, "not_found", "No such artifact.")
    return Response(session.get_one(Blob, row.sha256).data, media_type=row.content_type)


# --------------------------------------------------------------------- calls


@router.put("/runs/{run_id}/calls/{n}")
def put_call(
    run_id: UUID, n: Annotated[int, Path(ge=1)], body: ToolCallIn, who: Writer, session: SessionDep
) -> dict[str, Any]:
    run = owned_run(session, run_id, who)
    payload = body.payload()
    payload.pop("output", None)
    sha = store_blob(session, body.output.encode())
    row = session.get(Call, (run.id, n))
    if row is not None and row.payload == payload and row.sha256 == sha:
        return payload | {"n": n}
    if row is None:
        row = Call(run_id=run.id, n=n)
        session.add(row)
    row.payload, row.sha256 = payload, sha
    feed(session, Change(user_id=who.user.id, kind="call", ref=f"{run.id}/{n}", run_id=run.id))
    session.commit()
    return payload | {"n": n}


@router.get("/runs/{run_id}/calls")
def list_calls(run_id: UUID, who: Reader, session: SessionDep) -> dict[str, Any]:
    run = visible_run(session, run_id, who)
    rows = session.scalars(select(Call).where(Call.run_id == run.id).order_by(Call.n))
    return {"items": [row.payload | {"n": row.n} for row in rows], "next_cursor": None}


@router.get("/runs/{run_id}/calls/{n}/output")
def get_call_output(run_id: UUID, n: int, who: Reader, session: SessionDep) -> Response:
    run = visible_run(session, run_id, who)
    row = session.get(Call, (run.id, n))
    if row is None:
        raise fail(404, "not_found", "No such call.")
    return Response(session.get_one(Blob, row.sha256).data, media_type="text/plain; charset=utf-8")


# ----------------------------------------------- ruling, settlement, the rest


@router.put("/runs/{run_id}/ruling")
def put_ruling(run_id: UUID, body: RulingIn, who: Writer, session: SessionDep) -> dict[str, Any]:
    run = owned_run(session, run_id, who)
    payload = body.payload()
    row = session.get(Ruling, run.id)
    if row is not None:
        if row.payload != payload:
            raise fail(
                409, "conflict", "This run already has a different ruling, which cannot change."
            )
        return payload
    session.add(
        Ruling(
            run_id=run.id,
            ruled_at=parse_time(body.ruled_at),
            direction=body.direction,
            probability=body.probability,
            confidence=body.confidence,
            target_low=body.target_low,
            target_likely=body.target_likely,
            target_high=body.target_high,
            check_date=body.check_date,
            action=body.action,
            model=body.model,
            reference_date=body.reference_date,
            reference_close=body.reference_close,
            payload=payload,
        )
    )
    run.status = "ruled"
    feed(session, Change(user_id=who.user.id, kind="ruling", ref=run.id, run_id=run.id))
    session.commit()
    return payload


@router.put("/runs/{run_id}/settlement")
def put_settlement(
    run_id: UUID, body: SettlementIn, who: Writer, session: SessionDep
) -> dict[str, Any]:
    run = owned_run(session, run_id, who)
    payload = body.payload()
    row = session.get(Settlement, run.id)
    if row is not None:
        if row.payload != payload:
            raise fail(
                409,
                "conflict",
                "This run already has a different settlement, which cannot change.",
            )
        return payload
    session.add(Settlement(run_id=run.id, settled_at=parse_time(body.settled_at), payload=payload))
    feed(session, Change(user_id=who.user.id, kind="settlement", ref=run.id, run_id=run.id))
    session.commit()
    return payload


@router.put("/runs/{run_id}/followups/{followup_id}")
def put_followup(
    run_id: UUID, followup_id: UUID, body: FollowupIn, who: Writer, session: SessionDep
) -> dict[str, Any]:
    run = owned_run(session, run_id, who)
    payload = body.payload()
    row = session.get(Followup, str(followup_id))
    if row is not None and row.run_id != run.id:
        raise fail(409, "conflict", "This follow-up belongs to another run.")
    if row is None or row.payload != payload:
        if row is None:
            row = Followup(id=str(followup_id), run_id=run.id)
            session.add(row)
        row.at, row.payload = parse_time(body.at), payload
        feed(session, Change(user_id=who.user.id, kind="followup", ref=row.id, run_id=run.id))
        session.commit()
    return payload | {"id": row.id}


@router.get("/runs/{run_id}/followups")
def list_followups(run_id: UUID, who: Reader, session: SessionDep) -> dict[str, Any]:
    run = visible_run(session, run_id, who)
    rows = session.scalars(select(Followup).where(Followup.run_id == run.id).order_by(Followup.at))
    return {"items": [row.payload | {"id": row.id} for row in rows], "next_cursor": None}


@router.put("/runs/{run_id}/standings/{as_of}")
def put_standing(
    run_id: UUID, as_of: Day, body: StandingIn, who: Writer, session: SessionDep
) -> dict[str, Any]:
    run = owned_run(session, run_id, who)
    payload = body.payload()
    row = session.get(Standing, (run.id, as_of))
    if row is None or row.payload != payload:
        if row is None:
            row = Standing(run_id=run.id, as_of=as_of)
            session.add(row)
        row.payload = payload
        feed(
            session,
            Change(user_id=who.user.id, kind="standing", ref=f"{run.id}/{as_of}", run_id=run.id),
        )
        session.commit()
    return standing_out(row)


@router.get("/runs/{run_id}/standings")
def list_standings(run_id: UUID, who: Reader, session: SessionDep) -> dict[str, Any]:
    run = visible_run(session, run_id, who)
    rows = session.scalars(
        select(Standing).where(Standing.run_id == run.id).order_by(Standing.as_of)
    )
    return {"items": [standing_out(row) for row in rows], "next_cursor": None}


@router.put("/runs/{run_id}/reflections/{reflection_id}")
def put_reflection(
    run_id: UUID, reflection_id: UUID, body: ReflectionIn, who: Writer, session: SessionDep
) -> dict[str, Any]:
    run = owned_run(session, run_id, who)
    payload = body.payload()
    row = session.get(Reflection, str(reflection_id))
    if row is not None and row.run_id != run.id:
        raise fail(409, "conflict", "This reflection belongs to another run.")
    if row is None or row.payload != payload:
        if row is None:
            row = Reflection(id=str(reflection_id), run_id=run.id)
            session.add(row)
        row.at, row.payload = parse_time(body.at), payload
        feed(session, Change(user_id=who.user.id, kind="reflection", ref=row.id, run_id=run.id))
        session.commit()
    return payload | {"id": row.id}


# ------------------------------------------------- watchlist and start-overs


def watch_out(row: Watch) -> dict[str, Any]:
    return row.payload | {"ticker": row.ticker, "updated_at": format_time(row.updated_at)}


@router.get("/watchlist")
def list_watchlist(who: Reader, session: SessionDep) -> dict[str, Any]:
    rows = session.scalars(
        select(Watch).where(Watch.user_id == who.user.id).order_by(Watch.ticker)
    )
    return {"items": [watch_out(row) for row in rows], "next_cursor": None}


@router.put("/watchlist/{ticker}")
def put_watch(ticker: str, body: WatchIn, who: Writer, session: SessionDep) -> dict[str, Any]:
    payload = body.payload()
    row = session.get(Watch, (who.user.id, ticker))
    if row is None or row.payload != payload:
        if row is None:
            row = Watch(user_id=who.user.id, ticker=ticker)
            session.add(row)
        row.payload, row.updated_at = payload, now()
        feed(session, Change(user_id=who.user.id, kind="watchlist", ref=ticker))
        session.commit()
    return watch_out(row)


@router.delete("/watchlist/{ticker}", status_code=204)
def delete_watch(ticker: str, who: Writer, session: SessionDep) -> Response:
    row = session.get(Watch, (who.user.id, ticker))
    if row is None:
        raise fail(404, "not_found", "That ticker is not on your watchlist.")
    session.delete(row)
    feed(session, Change(user_id=who.user.id, kind="watchlist", ref=ticker, op="delete"))
    session.commit()
    return Response(status_code=204)


@router.get("/me/start-overs")
def list_start_overs(who: Reader, session: SessionDep) -> dict[str, Any]:
    rows = session.scalars(
        select(StartOver).where(StartOver.user_id == who.user.id).order_by(StartOver.at)
    )
    return {"items": [row.payload | {"id": row.id} for row in rows], "next_cursor": None}


@router.put("/me/start-overs/{start_over_id}")
def put_start_over(
    start_over_id: UUID, body: StartOverIn, who: Writer, session: SessionDep
) -> dict[str, Any]:
    payload = body.payload()
    row = session.get(StartOver, str(start_over_id))
    if row is not None and row.user_id != who.user.id:
        raise fail(403, "forbidden", "This start-over belongs to another user.")
    if row is None or row.payload != payload:
        if row is None:
            row = StartOver(id=str(start_over_id), user_id=who.user.id)
            session.add(row)
        row.at, row.payload = parse_time(body.at), payload
        feed(session, Change(user_id=who.user.id, kind="start_over", ref=row.id))
        session.commit()
    return payload | {"id": row.id}


# ---------------------------------------------------------------------- jobs


@router.put("/jobs/{job_id}")
def put_job(job_id: UUID, body: JobIn, who: Writer, session: SessionDep) -> dict[str, Any]:
    payload = body.payload()
    row = session.get(Job, str(job_id))
    if row is not None and row.user_id != who.user.id:
        raise fail(403, "forbidden", "This job belongs to another user.")
    if row is not None and row.payload == payload:
        return job_out(session, row)
    if row is None:
        row = Job(id=str(job_id), user_id=who.user.id, created_at=now())
        session.add(row)
    row.kind, row.status, row.ticker, row.run_id = body.kind, body.status, body.ticker, body.run
    row.machine_id = body.machine or who.machine_id
    row.payload, row.updated_at = payload, now()
    feed(session, Change(user_id=who.user.id, kind="job", ref=row.id, run_id=row.run_id))
    session.commit()
    return job_out(session, row)


def _jobs(who: Caller) -> Select[Any]:
    """Jobs the caller may read: their own, and those of runs they may read."""
    return (
        select(Job)
        .outerjoin(Run, Run.id == Job.run_id)
        .where(or_(Job.user_id == who.user.id, readable(who.user.id)))
    )


@router.get("/jobs")
def list_jobs(
    who: Reader, session: SessionDep, wanted: Annotated[JobQuery, Query()]
) -> dict[str, Any]:
    query = _jobs(who)
    if wanted.status:
        query = query.where(Job.status == wanted.status)
    if wanted.kind:
        query = query.where(Job.kind == wanted.kind)
    if wanted.ticker:
        query = query.where(Job.ticker == wanted.ticker)
    if wanted.user:
        query = query.join(User, User.id == Job.user_id).where(User.handle == wanted.user)
    if wanted.machine:
        query = query.where(Job.machine_id == wanted.machine)
    rows, next_cursor = page(session, query, Job.updated_at, Job.id, wanted)
    return {"items": [job_out(session, row[0]) for row in rows], "next_cursor": next_cursor}


@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, who: Reader, session: SessionDep) -> dict[str, Any]:
    row = session.scalar(_jobs(who).where(Job.id == str(job_id)))
    if row is None:
        raise fail(404, "not_found", "No such job.")
    return job_out(session, row)
