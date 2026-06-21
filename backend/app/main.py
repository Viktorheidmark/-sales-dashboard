from fastapi import FastAPI

app = FastAPI(title="Solvigo Sales Dashboard API")


@app.get("/health")
def health():
    return {"status": "ok", "service": "solvigo-api"}
