from fastapi import FastAPI

from db import get_cursor

app = FastAPI(title="Trendcast API")


@app.get("/health")
def health():
    with get_cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return {"status": "ok"}
