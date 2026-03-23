from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")

    # Ежечасная сводка метрик
    scheduler.add_job(
        _run_hourly,
        trigger=CronTrigger(minute=0),  # каждый час в 0 минут
        id="hourly_report",
        name="Hourly Telegram Report",
        misfire_grace_time=300
    )

    # Ежедневный отчёт с гипотезами в 00:00 МСК (итоги дня)
    scheduler.add_job(
        _run_daily,
        trigger=CronTrigger(hour=0, minute=0),
        id="daily_report",
        name="Daily Claude Hypotheses Report",
        misfire_grace_time=600
    )

    scheduler.start()
    logger.info("Scheduler started: hourly (every hour) + daily (09:00 MSK)")
    return scheduler


def _run_hourly():
    try:
        from bot.hourly_report import run
        run()
    except Exception as e:
        logger.error(f"Hourly report failed: {e}")


def _run_daily():
    try:
        from bot.daily_report import run
        run()
    except Exception as e:
        logger.error(f"Daily report failed: {e}")
