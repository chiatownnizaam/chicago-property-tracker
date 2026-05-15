# Chicago Property Tracker

Web application that tracks home prices, foreclosures, evictions, bank seizures, and price drops for properties in **Chicago, Lincolnwood, Sauganash, Skokie, and Evanston, IL**.

## Stack

- **Backend:** FastAPI · SQLAlchemy · PostgreSQL · APScheduler · httpx + tenacity
- **Frontend:** React · Vite · React Router · Leaflet · Recharts · Tailwind
- **Data sources:** Cook County Open Data Portal (Socrata) · Chicago Data Portal · Redfin · Realtor.com

## Features

- Dashboard with stats by city and event-type chart
- Interactive map with color-coded markers (foreclosure / eviction / seizure / normal)
- Filterable tables for foreclosures, evictions, bank seizures, sales
- **Price drops** page (Redfin + Realtor) showing reductions over a chosen time window
- Per-property detail page with full event timeline, sales-price history chart, and active-listing price chart
- Nightly scheduled ingest (02:00 America/Chicago) + 6-hourly listings refresh

## Quick start

```bash
# Backend
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env       # then edit and add your Chicago Data Portal app token

# Database (Postgres 16)
/usr/local/opt/postgresql@16/bin/createdb chicago_property_tracker
./venv/bin/python -c "from app.database import engine, Base; from app.models import *; Base.metadata.create_all(bind=engine)"

# Seed sample data (skip if running real ingest)
./venv/bin/python -m app.scrapers.seed

# Start the API
./venv/bin/uvicorn app.main:app --reload
```

```bash
# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

- Dashboard:  http://localhost:3000
- API docs:   http://localhost:8000/docs

## Live data ingest

```bash
cd backend
./venv/bin/python -m app.scrapers.ingest             # Cook County sales + tax sales
./venv/bin/python -m app.scrapers.listings_ingest    # Redfin + Realtor (price drops)
```

The scheduler runs both automatically once the backend is up. Disable with `RUN_SCHEDULER=false` in `.env`.

## Project layout

```
backend/
  app/
    constants.py            ← tracked cities (single source of truth)
    main.py                 ← FastAPI app + lifespan
    config.py               ← settings (.env)
    database.py             ← SQLAlchemy engine + session
    scheduler.py            ← APScheduler nightly + 6h jobs
    models/                 ← Property, Sale, Foreclosure, Eviction, BankSeizure, Listing, PriceHistory
    schemas/                ← Pydantic request/response models
    routers/                ← FastAPI endpoints
    scrapers/               ← Cook County, Redfin, Realtor, seed
    utils/
      normalize.py          ← address/PIN/Decimal/SoQL helpers
      http.py               ← shared retry-aware HTTP client

frontend/
  src/
    App.jsx
    main.jsx
    index.css
    services/api.js
    components/             ← PropertyCell, FilterBar, DataTable, StatCard
    pages/                  ← Dashboard, MapView, PriceDropsPage, PropertyDetail, ForeclosuresPage, EvictionsPage, BankSeizuresPage, SalesPage
```

## Data integrity

- All money columns are `Numeric(14, 2)` — no float drift
- Addresses are normalized (uppercase, abbreviated suffixes) and used as the dedup key
- PINs are stripped to digits before insert/lookup (handles both `10-12-345-678-9000` and `1012345678000`)
- Per-record SAVEPOINTs in every ingest — one bad row can't kill the batch
- SoQL queries use parameterized escaping
- Retry/backoff (tenacity 4x exponential) on all external HTTP calls

## Notes on data availability

| Source | Status |
|---|---|
| Cook County property sales (`wvhk-k5uv`) | ✅ Live |
| Cook County parcel addresses (`3723-97qp`) | ✅ Live |
| Cook County tax sales (`55ju-2fs9`) | ✅ Live |
| Foreclosure filings | ⚠️ Only archived 2011–2015 data in Cook County portal; current data is at the Circuit Court Clerk only |
| Eviction filings | ⚠️ Not in any open-data portal — Circuit Court Clerk only |
| Redfin / Realtor active listings | ✅ Live (subject to those sites' ToS — keep request rates low) |
