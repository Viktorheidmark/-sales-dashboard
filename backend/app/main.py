from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import dashboard, suppliers, chat

app = FastAPI(
    title="Solvigo Sales Dashboard API",
    description="Supplier-scoped retail analytics API backed by the MCP query layer.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(suppliers.router)
app.include_router(dashboard.router)
app.include_router(chat.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "solvigo-api"}
