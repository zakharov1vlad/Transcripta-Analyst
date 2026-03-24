from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")

    # Ежечасная сводка метрик
    scheduler.add_job(
        _run_hourly,
        trigger=CronTrigger(minute=0),
        id="hourly_report",
        name="Hourly Telegram Report",
        misfire_grace_time=300
    )

    scheduler.start()
    logger.info("Scheduler started: hourly report every hour")
    return scheduler


def _run_hourly():
    try:
        from bot.hourly_report import run
        run()
    except Exception as e:
        logger.error(f"Hourly report failed: {e}")
