from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.models import Property, Sale, Foreclosure, Eviction, BankSeizure, Listing, PriceHistory
from app.routers import properties, foreclosures, evictions, bank_seizures, sales, listings
from app.scheduler import start_scheduler, stop_scheduler

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Chicago Property Tracker",
    description="Track home prices, foreclosures, evictions, and bank seizures in Chicago, Lincolnwood, Sauganash, and Skokie, IL",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(properties.router, prefix="/api/v1")
app.include_router(foreclosures.router, prefix="/api/v1")
app.include_router(evictions.router, prefix="/api/v1")
app.include_router(bank_seizures.router, prefix="/api/v1")
app.include_router(sales.router, prefix="/api/v1")
app.include_router(listings.router, prefix="/api/v1")


@app.get("/")
def root():
    return {"message": "Chicago Property Tracker API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
