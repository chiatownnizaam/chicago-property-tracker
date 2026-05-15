"""
Nightly ingest scheduling via APScheduler.

The scheduler starts when the FastAPI app starts (lifespan event), and runs:
  - Cook County / Chicago Data Portal ingest at 02:00 every day
  - Redfin / Realtor listings ingest every 6 hours

If you don't want background ingest in your app process (e.g. you want to run
it via system cron / launchd instead), set RUN_SCHEDULER=false in .env.
"""
import logging
import os
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _run_data_portal_ingest():
    from app.scrapers.ingest import run_full_ingest
    try:
        run_full_ingest()
    except Exception as e:
        log.exception(f"Data portal ingest failed: {e}")


def _run_listings_ingest():
    from app.scrapers.listings_ingest import run_listings_ingest
    try:
        run_listings_ingest()
    except Exception as e:
        log.exception(f"Listings ingest failed: {e}")


def _run_fred_ingest():
    from app.scrapers.fred import run_fred_ingest
    try:
        run_fred_ingest()
    except Exception as e:
        log.exception(f"FRED ingest failed: {e}")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    if os.getenv("RUN_SCHEDULER", "true").lower() in ("false", "0", "no"):
        log.info("Scheduler disabled by RUN_SCHEDULER env var.")
        return None

    scheduler = BackgroundScheduler(timezone="America/Chicago")

    scheduler.add_job(
        _run_data_portal_ingest,
        trigger=CronTrigger(hour=2, minute=0),
        id="data_portal_nightly",
        name="Cook County + Chicago Data Portal nightly ingest",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_listings_ingest,
        trigger=IntervalTrigger(hours=6),
        id="listings_periodic",
        name="Redfin + Realtor listings (price-drop check) every 6h",
        replace_existing=True,
        next_run_time=None,  # don't run immediately on startup
    )

    # FRED data is quarterly/weekly — a single weekly run is plenty.
    scheduler.add_job(
        _run_fred_ingest,
        trigger=CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="fred_weekly",
        name="FRED macro metrics weekly refresh",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    log.info("Background scheduler started.")
    for job in scheduler.get_jobs():
        log.info(f"  Job '{job.name}' next run: {job.next_run_time}")
    return scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
