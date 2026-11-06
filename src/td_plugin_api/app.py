from fastapi import FastAPI

app = FastAPI(title="TD Plugin API")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
