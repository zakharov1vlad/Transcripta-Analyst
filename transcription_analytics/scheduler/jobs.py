from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")

    # Ежедневный отчёт в 09:00 МСК
    scheduler.add_job(
        _run_daily,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_report",
        name="Daily Telegram Report",
        misfire_grace_time=600
    )

    scheduler.start()
    logger.info("Scheduler started: daily report at 09:00 MSK")
    return scheduler


def _run_daily():
    try:
        from bot.hourly_report import run
        run()
    except Exception as e:
        logger.error(f"Daily report failed: {e}")
