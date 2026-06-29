from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, dashboard, suppliers, chat, insights

app = FastAPI(
    title="Solvigo Sales Dashboard API",
    description="Supplier-scoped retail analytics API backed by the MCP query layer.",
    version="0.1.0",
)

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(suppliers.router)
app.include_router(dashboard.router)
app.include_router(chat.router)
app.include_router(insights.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "solvigo-api"}
