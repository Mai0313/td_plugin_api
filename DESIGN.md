# API design

The agreed design of the v1 API, written before the code. A change to it is agreed with the owner first and then made here and in the code together.

## What the server is for

The tradingagents plugin runs analyses on its users' machines and records the facts of each call. This server stores those records and serves them to every machine and to read-only consumers, such as a Discord bot that only reads calls. It replaces the plugin's git sync as the way records are shared; the plugin keeps git as a backup.

- **Facts only.** The server stores what clients send and computes nothing about the market: no measuring, no settling, no track-record scores, no rule for which call supersedes which. Clients compute those and upload the results a reader needs (standings and settlements below).
- **Local first.** A client writes its record locally and uploads when it can, so every write is idempotent: IDs are made by the client, writes are `PUT` to the record's own URL, and sending the same body again changes nothing.
- **Typed columns for what is queried, the whole record as JSON.** Each record keeps the fields readers filter or sort by as columns and its whole body, unknown fields included, as a JSON `payload`. A field the plugin adds later is stored and served without a server change or a migration.
- **Not shaped around one agent host.** Anything only one host has, such as an Antigravity conversation ID, goes into `client_meta`, which the server stores and returns without reading it.

## Conventions

- Every path starts with `/v1`. A breaking change gets `/v2`; adding a field is not breaking.
- JSON in and out, except artifact and tool-output bodies, which are sent and served as they are.
- Times are UTC ISO 8601 (`2026-11-05T17:04:50Z`); dates are `YYYY-MM-DD` in the stock's market.
- IDs are UUIDv7 strings made by the client, except a machine's, which is the 12-character ID the plugin already keeps in `.machine-id`.
- `Authorization: Bearer <token>` on every request but `/healthz` and the API's own generated docs (`/docs`, `/redoc`, `/openapi.json`), which describe only its shape.
- Lists return `{"items": [...], "next_cursor": ...}`; they take `limit` and `cursor`, and `next_cursor` is null on the last page.
- Errors are `{"error": {"code": "...", "message": "..."}}`: 401 for a missing or bad token, 403 for a record that is not yours or a missing scope, 404 for one that does not exist or is not visible to you, 409 for a different body sent for a record that cannot change, 422 for a malformed body.
- A `PUT` whose body matches what is stored returns 200 and records no change.

## Users, tokens and machines

There is no sign-up: the owner creates users and tokens with commands on the server: `td_plugin_api admin create-user`, `create-token` (prints the token's ID and the token, once) and `revoke-token`.

- **User**: `id`, `handle`, `display_name`, `role` (`owner` or `member`), `created_at`.
- **Token**: belongs to a user and optionally to one of their machines; `name`, `scopes` (`read`, `write`), `created_at`, `last_used_at`, `revoked_at`. It is shown once, as `tdp_` followed by random characters, and the server keeps only its hash. Each machine gets its own token so one can be revoked alone, and a read-only consumer gets a `read` token.
- **Machine**: `id`, `host`, `settings` and `status` (JSON the server does not read, such as the plugin's models, language and follow-up schedule), `seen_at`.

| Method | Path                | What it does                                         |
| ------ | ------------------- | ---------------------------------------------------- |
| GET    | `/v1/me`            | the token's user, scopes and machine                 |
| GET    | `/v1/machines`      | your machines                                        |
| PUT    | `/v1/machines/{id}` | settings and status; every write is also a heartbeat |

## The record

What clients write, mirroring the plugin's data folder.

```
users ── machines ── tokens
  ├── runs ──┬── ruling        0..1, cannot change once written
  │          ├── artifacts     reports/*.md, debate.md, decision.md, summary.json, ...
  │          ├── calls         the data tools' calls, each with its output
  │          ├── followups
  │          ├── standings     one per day measured
  │          ├── settlement    0..1, cannot change once written
  │          └── reflections
  ├── jobs                     what is being worked on right now
  ├── watchlist
  └── start_overs
```

### Runs

A run is one analysis, whether or not it reached a ruling. Columns: `id`, `slug` (the plugin's folder name, such as `NVDA_2026-11-05_151145`), `user`, `machine`, `ticker`, `benchmark`, `status` (`running`, `ruled`, `failed`, `abandoned`), `visibility` (`public` or `private`), `has_holding`, `language`, `host`, `model`, `plugin_version`, `client_meta`, `created_at`, `finished_at`, `deleted_at`.

- `visibility` defaults to `public`; a run with `has_holding` true is private whatever `visibility` says (see [Visibility](#visibility)).
- `language` is the language the run's files are written in. A run sent without one is stored as `Traditional Chinese`.
- `model` is the model that chaired the run.
- `machine` defaults to the machine of the token that created the run.

| Method | Path            | What it does                                                                     |
| ------ | --------------- | -------------------------------------------------------------------------------- |
| PUT    | `/v1/runs/{id}` | create or update                                                                 |
| GET    | `/v1/runs`      | filter by `ticker`, `user`, `model`, `status`, `since`                           |
| GET    | `/v1/runs/{id}` | the run with its ruling and settlement, and the lists of what else belongs to it |
| DELETE | `/v1/runs/{id}` | marks it deleted: it disappears from every read but stays stored                 |

### Artifacts

A file the run wrote, at its path inside the run folder. Columns: `path`, `content_type`, `sha256`, `size`, `role` and `model` (who wrote it, when known), `updated_at`. Bodies are stored once per content hash, so the same text sent twice takes no extra space.

| Method | Path                             | What it does                                                                              |
| ------ | -------------------------------- | ----------------------------------------------------------------------------------------- |
| PUT    | `/v1/runs/{id}/artifacts/{path}` | the body is the file, its type the `Content-Type`; `role` and `model` as query parameters |
| GET    | `/v1/runs/{id}/artifacts`        | the list                                                                                  |
| GET    | `/v1/runs/{id}/artifacts/{path}` | the file                                                                                  |

### Calls

One data-tool call: `n` (its number in the run, as in `data/007-get_fundamentals.md`), `at`, `role`, `tool`, `params`, `error`, and its output, stored by content hash like an artifact body, so the same output fetched by two runs is stored once.

| Method | Path                             | What it does                  |
| ------ | -------------------------------- | ----------------------------- |
| PUT    | `/v1/runs/{id}/calls/{n}`        | JSON with an `output` string  |
| GET    | `/v1/runs/{id}/calls`            | the list, without the outputs |
| GET    | `/v1/runs/{id}/calls/{n}/output` | the output                    |

### Ruling

The ruling the plugin records, whole, as the payload, with these columns: `ruled_at`, `direction`, `probability`, `confidence`, `target_low`, `target_likely`, `target_high`, `check_date`, `action`, `model`, `reference_date`, `reference_close`. Writing it sets the run's status to `ruled`.

`PUT /v1/runs/{id}/ruling`; it is read through the run or the call.

### Follow-ups

`id`, `at`, `verdict` (`holding`, `warning`, `invalidated`), `note` (the one or two sentences a list shows), `body` (the full text, the section the plugin appends to `followups.md`), `model`.

`PUT /v1/runs/{id}/followups/{followup_id}`, `GET /v1/runs/{id}/followups`.

### Standings

Where an open call stands as of a day, measured by a client the way settling will score it: `as_of`, the measure's result as the payload (`entry_date`, `exit_date`, `return_pct`, `benchmark_return_pct`, `excess_return_pct`, `direction_hit`, `close`, `in_range`), and `method`, naming the measure that produced it. There is one per run and day, and a later `PUT` for the same day replaces it, so a client may measure again. This is how a reader that computes nothing gets numbers. A standing is only as fresh as the last client that measured, so a reader shows its `as_of` beside it.

`PUT /v1/runs/{id}/standings/{as_of}`, `GET /v1/runs/{id}/standings`.

### Settlement

The settlement the plugin records, whole: `settled_at` and the measure's result as of the check date. It cannot change once written.

`PUT /v1/runs/{id}/settlement`.

### Reflections

`id`, `at`, `text`, `lesson`. `PUT /v1/runs/{id}/reflections/{reflection_id}`.

### Jobs

Work a client is doing or has queued, so any reader can tell what is being processed and how far it has got: an analysis, a follow-up, or any later kind of work. Columns: `id`, `user`, `machine`, `kind` (free text such as `analysis` or `followup`, so a new kind needs no server change), `ticker`, `run` (the run it produces or works on, once there is one), `status` (`queued`, `running`, `done`, `failed`, `cancelled`), `stage` and `detail` (free text the client sets as it moves on, such as `debate` and `Round 2`), `error`, `created_at`, `started_at`, `updated_at`, `finished_at`.

- Every update is a change on the feed, so a reader on `/v1/events` sees each stage as it is reached.
- The server never decides that a job died. A job whose `updated_at` and machine `seen_at` are both old may have stopped, and the reader says so.

| Method | Path            | What it does                                            |
| ------ | --------------- | ------------------------------------------------------- |
| PUT    | `/v1/jobs/{id}` | create or update                                        |
| GET    | `/v1/jobs`      | filter by `status`, `kind`, `ticker`, `user`, `machine` |
| GET    | `/v1/jobs/{id}` | one job                                                 |

### Watchlist

One row per user and ticker: `watched`, `follow`, `holding` (free text), `updated_at`. Private to its user.

| Method | Path                     | What it does  |
| ------ | ------------------------ | ------------- |
| GET    | `/v1/watchlist`          | your rows     |
| PUT    | `/v1/watchlist/{ticker}` | the whole row |
| DELETE | `/v1/watchlist/{ticker}` | removes it    |

### Start-overs

`PUT /v1/me/start-overs/{id}` with `{"at": ...}` records the moment a user started their record over. Reads of that user's calls then leave out the ones ruled before their latest start-over, unless asked for with `all=true`. Nothing is deleted. `GET /v1/me/start-overs` lists them.

## Reading calls

A reader that only wants the AI's calls, such as the Discord bot, should not have to put a run, its ruling, summary, follow-ups, standing and settlement together itself. These endpoints do it: a call is a run with a ruling that is not deleted, joined with what belongs to it. They combine stored records and compute nothing.

| Method | Path                         | What it does                                                                                                   |
| ------ | ---------------------------- | -------------------------------------------------------------------------------------------------------------- |
| GET    | `/v1/calls`                  | filter by `ticker`, `user`, `model`, `status` (`open` or `settled`), `since` (ruled at or after); newest first |
| GET    | `/v1/calls/{id}`             | one call                                                                                                       |
| GET    | `/v1/tickers/{ticker}/calls` | a ticker's calls, newest first; `latest=true` keeps only the newest (of the given `model`, when one is given)  |

A call is `settled` once its settlement is stored and `open` before. `include=key_points,invalidation,followups,standings` adds those lists; long texts stay behind `links`. With made-up values:

```json
{
  "id": "0193a0c4-7d2e-7c3a-9f10-2b6d8e4a1c55",
  "slug": "NVDA_2026-11-05_151145",
  "ticker": "NVDA",
  "benchmark": "SPY",
  "user": "wei",
  "model": "example-model",
  "language": "Traditional Chinese",
  "ruled_at": "2026-11-05T07:30:00Z",
  "check_date": "2026-11-27",
  "status": "open",
  "direction": "bullish",
  "probability": 0.6,
  "action": "wait",
  "target": {
    "low": 180.0,
    "likely": 195.0,
    "high": 210.0
  },
  "wrong_below": 175.0,
  "wrong_above": null,
  "what_to_do": "...",
  "latest_followup": {
    "at": "2026-11-06T22:00:00Z",
    "verdict": "holding",
    "note": "..."
  },
  "latest_standing": {
    "as_of": "2026-11-06",
    "return_pct": 1.2,
    "benchmark_return_pct": 0.4,
    "excess_return_pct": 0.8,
    "direction_hit": false,
    "close": 188.5,
    "in_range": true
  },
  "settlement": null,
  "links": {
    "run": "/v1/runs/0193a0c4-7d2e-7c3a-9f10-2b6d8e4a1c55",
    "decision": "/v1/runs/0193a0c4-7d2e-7c3a-9f10-2b6d8e4a1c55/artifacts/decision.md"
  }
}
```

## Changes and events

Every write that changes something takes the next number in one sequence, handed out in commit order, and clients follow it in two ways:

- `GET /v1/changes?after=<seq>`: what changed after a number, oldest first, each entry `{seq, at, kind, run, ref, op}`, narrowed by `types=` and paged by `limit`, with `next_cursor` as the next page's `after`. A client that was offline catches up from the last number it saw.
- `GET /v1/events`: the same entries as server-sent events as they happen, with `seq` as the event ID, so a dropped connection resumes from `Last-Event-ID` without missing any. `types=` narrows it, such as `types=ruling,followup,standing,settlement` for a bot that posts new calls, or `types=job` for one that shows what is being processed. A comment line goes out every 30 seconds so proxies keep the connection open.

A reader sees only the changes to records it may read, plus the delete of a public run, so a reader that copied the run drops it.

## Visibility

- Private to its user: tokens, machines, the watchlist (holdings included), start-overs, and private runs.
- Everything belonging to a public run is readable by every user: its ruling, artifacts, calls, follow-ups, standings, settlement and reflections.
- A job is readable by whoever may read its run, and one with no run yet only by its user.
- A run with `has_holding` true is private. A holding the user gave reaches the risk critic and the ruling's plain-words advice, so it shows up in `debate.md`, `decision.md`, `summary.json`, the follow-up texts and the ruling's `action` (`add`, `hold`, `reduce`), and model-written text cannot be split reliably into a private part and a shareable one.
- Only a record's owner writes it.

## Storage

PostgreSQL beside the app in Docker Compose: payloads as `jsonb`, and artifact and tool-output bodies in one table keyed by SHA-256. The bodies can move to files or object storage later without changing the API.

## Reserved for later

Designed now so the paths stay free, and not built in v1:

- `GET /v1/market-data?tool=&params=&as_of=`: the output of a data-tool call another run already made that day, so a client can skip the fetch.
- `PUT` and `GET /v1/calls/{id}/advice`: a user's own add, hold or reduce advice on any call, private to them. Once the plugin analyses without the holding and writes the advice as a separate step, a run no longer has to be private for carrying a holding, and anyone can get advice on a shared call with their own holding.
- Invitations and sign-in with GitHub, once other people use it.
- Webhooks, for a consumer that cannot hold an event stream open.
