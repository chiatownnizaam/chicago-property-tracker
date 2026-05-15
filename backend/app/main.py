import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base
from app.models import Property, Sale, Foreclosure, Eviction, BankSeizure, Listing, PriceHistory, User
from app.routers import properties, foreclosures, evictions, bank_seizures, sales, listings, auth
from app.auth.deps import get_current_user
from app.scheduler import start_scheduler, stop_scheduler

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Chicago Property Tracker",
    description="Track home prices, foreclosures, evictions, and bank seizures in Chicago, Lincolnwood, Sauganash, Skokie, and Evanston, IL",
    version="1.0.0",
    lifespan=lifespan,
)

# Wire slowapi's rate limiter (used by /auth/login)
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public auth endpoints — no dependency
app.include_router(auth.router)

# Business endpoints — every route requires get_current_user
api_deps = [Depends(get_current_user)]
app.include_router(properties.router, prefix="/api/v1", dependencies=api_deps)
app.include_router(foreclosures.router, prefix="/api/v1", dependencies=api_deps)
app.include_router(evictions.router, prefix="/api/v1", dependencies=api_deps)
app.include_router(bank_seizures.router, prefix="/api/v1", dependencies=api_deps)
app.include_router(sales.router, prefix="/api/v1", dependencies=api_deps)
app.include_router(listings.router, prefix="/api/v1", dependencies=api_deps)


@app.get("/health")
def health():
    return {"status": "ok"}


# ----- Serve the built React bundle when present ---------------------------
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Anything that isn't /auth, /api, /health, /docs, /assets falls through
        # to index.html so React Router can handle the route.
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"error": "frontend bundle not built"}
else:
    @app.get("/")
    def root():
        return {
            "message": "Chicago Property Tracker API",
            "docs": "/docs",
            "frontend": "not built — run `npm run build` in frontend/",
        }
