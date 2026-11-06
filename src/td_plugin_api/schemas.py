"""What clients send.

Every model keeps fields it does not know, so a field the plugin adds later is stored and served unchanged. Times and dates stay the strings the client sent, checked here, so the stored record is the one the client wrote.
"""

from typing import Any, Literal, Annotated
from datetime import date, datetime

from pydantic import Field, BaseModel, ConfigDict, AfterValidator


def _time(text: str) -> str:
    if datetime.fromisoformat(text).tzinfo is None:
        raise ValueError("a time needs an offset, such as Z or +00:00")
    return text


def _day(text: str) -> str:
    date.fromisoformat(text)
    return text


Time = Annotated[str, AfterValidator(_time)]
Day = Annotated[str, AfterValidator(_day)]


class Record(BaseModel):
    model_config = ConfigDict(extra="allow")

    def payload(self) -> dict[str, Any]:
        """The record as the client sent it."""
        return self.model_dump(mode="json", exclude_unset=True)


class MachineIn(Record):
    host: str = ""
    settings: dict[str, Any] = {}
    status: dict[str, Any] = {}


class RunIn(Record):
    ticker: str
    benchmark: str | None = None
    slug: str | None = None
    machine: str | None = None
    status: Literal["running", "ruled", "failed", "abandoned"] = "running"
    visibility: Literal["public", "private"] = "public"
    has_holding: bool = False
    language: str = "Traditional Chinese"
    host: str | None = None
    model: str | None = None
    plugin_version: str | None = None
    client_meta: dict[str, Any] | None = None
    created_at: Time | None = None
    finished_at: Time | None = None


class ToolCallIn(Record):
    at: Time
    role: str | None = None
    tool: str
    params: dict[str, Any] = {}
    error: str | None = None
    output: str


class RulingIn(Record):
    ruled_at: Time
    direction: Literal["bullish", "neutral", "bearish"]
    probability: float | None = None
    confidence: str | None = None
    target_low: float
    target_likely: float
    target_high: float
    check_date: Day
    action: str | None = None
    model: str | None = None
    reference_date: Day | None = None
    reference_close: float | None = None


class FollowupIn(Record):
    at: Time
    verdict: Literal["holding", "warning", "invalidated"]
    note: str = ""
    body: str | None = None
    model: str | None = None


class StandingIn(Record):
    method: str | None = None


class SettlementIn(Record):
    settled_at: Time


class ReflectionIn(Record):
    at: Time
    text: str
    lesson: str | None = None


class WatchIn(Record):
    watched: bool = True
    follow: bool = False
    holding: str = ""


class StartOverIn(Record):
    at: Time


class JobIn(Record):
    kind: str
    status: Literal["queued", "running", "done", "failed", "cancelled"]
    ticker: str | None = None
    run: str | None = None
    machine: str | None = None
    stage: str | None = None
    detail: str | None = None
    error: str | None = None
    started_at: Time | None = None
    finished_at: Time | None = None


class Paging(BaseModel):
    limit: int = Field(50, ge=1, le=500)
    cursor: str | None = None


class RunQuery(Paging):
    ticker: str | None = None
    user: str | None = None
    model: str | None = None
    status: str | None = None
    since: Time | None = None


class JobQuery(Paging):
    status: str | None = None
    kind: str | None = None
    ticker: str | None = None
    user: str | None = None
    machine: str | None = None


class CallQuery(Paging):
    ticker: str | None = None
    user: str | None = None
    model: str | None = None
    status: Literal["open", "settled"] | None = None
    since: Time | None = None
    # `all=true` keeps the calls a user's start-over hides.
    all_: bool = Field(False, alias="all")
    include: str | None = None
