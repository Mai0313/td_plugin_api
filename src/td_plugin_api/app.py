from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from td_plugin_api import reads, records
from td_plugin_api.db import database_url, open_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    engine, app.state.sessions = open_database(database_url())
    yield
    engine.dispose()


app = FastAPI(title="TD Plugin API", lifespan=lifespan)
app.include_router(records.router)
app.include_router(reads.router)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    detail = (
        exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": exc.detail}
    )
    return JSONResponse({"error": detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
    message = "; ".join(
        f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors()
    )
    return JSONResponse({"error": {"code": "invalid", "message": message}}, status_code=422)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
