"""Who is calling, what they may read, and the owner's commands for users and tokens."""

from typing import Annotated
import hashlib
import secrets
from dataclasses import dataclass
from collections.abc import Iterator

from fastapi import Header, Depends, Request, HTTPException
from sqlalchemy import or_, and_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from td_plugin_api.db import Run, User, Token, now

SCOPES = ("read", "write")


def fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message})


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@dataclass
class Caller:
    user: User
    scopes: set[str]
    machine_id: str | None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def caller(session: SessionDep, authorization: Annotated[str | None, Header()] = None) -> Caller:
    scheme, _, token = (authorization or "").partition(" ")
    row = None
    if scheme.lower() == "bearer" and token:
        row = session.scalar(
            select(Token).where(Token.token_hash == hash_token(token), Token.revoked_at.is_(None))
        )
    if row is None:
        raise fail(401, "unauthorized", "Send a valid token as `Authorization: Bearer <token>`.")
    row.last_used_at = now()
    user = session.get_one(User, row.user_id)
    # Nothing is loaded after this commit, so a long response such as the event stream holds no connection.
    session.commit()
    return Caller(user, set(row.scopes.split(",")), row.machine_id)


def writer(who: Annotated[Caller, Depends(caller)]) -> Caller:
    if "write" not in who.scopes:
        raise fail(403, "forbidden", "This token can only read.")
    return who


Reader = Annotated[Caller, Depends(caller)]
Writer = Annotated[Caller, Depends(writer)]


def readable(user_id: int) -> ColumnElement[bool]:
    """Runs the user may read: their own, and other users' public runs without a holding; never a deleted one."""
    return and_(
        Run.deleted_at.is_(None),
        or_(Run.user_id == user_id, and_(Run.visibility == "public", Run.has_holding.is_(False))),
    )


def create_user(
    session: Session, handle: str, display_name: str = "", role: str = "member"
) -> User:
    if session.scalar(select(User).where(User.handle == handle)) is not None:
        raise ValueError(f"User {handle!r} already exists.")
    user = User(handle=handle, display_name=display_name, role=role)
    session.add(user)
    session.commit()
    return user


def create_token(
    session: Session,
    handle: str,
    name: str,
    scopes: str = "read,write",
    machine: str | None = None,
) -> tuple[int, str]:
    """Make a token for a user and return its ID and the token; only its hash is kept, so this is the one time it is seen."""
    user = session.scalar(select(User).where(User.handle == handle))
    if user is None:
        raise ValueError(f"No user {handle!r}.")
    wanted = set(scopes.split(","))
    if not wanted <= set(SCOPES):
        raise ValueError(f"Scopes are {', '.join(SCOPES)}.")
    token = f"tdp_{secrets.token_urlsafe(32)}"
    row = Token(
        user_id=user.id,
        machine_id=machine,
        name=name,
        scopes=",".join(sorted(wanted)),
        token_hash=hash_token(token),
    )
    session.add(row)
    session.commit()
    return row.id, token


def revoke_token(session: Session, token_id: int) -> None:
    row = session.get(Token, token_id)
    if row is None:
        raise ValueError(f"No token {token_id}.")
    row.revoked_at = now()
    session.commit()
