"""
Transcripta Analytics — точка входа.

Запуск:
    cd transcription_analytics
    python main.py            # запускает планировщик + Streamlit дашборд
    python main.py --bot      # только Telegram бот + планировщик (без дашборда)
"""

import sys
import logging
import subprocess
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def run_scheduler_only():
    """Запускает только планировщик (TG бот + гипотезы)."""
    from scheduler.jobs import start_scheduler
    import time

    logger.info("Starting scheduler (Telegram reports + Claude hypotheses)...")
    scheduler = start_scheduler()

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")


def run_with_dashboard():
    """Запускает планировщик в фоне + Streamlit дашборд."""
    from scheduler.jobs import start_scheduler

    logger.info("Starting scheduler in background...")
    start_scheduler()

    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "app.py")
    logger.info(f"Launching Streamlit dashboard: {dashboard_path}")

    cmd = [sys.executable, "-m", "streamlit", "run", dashboard_path,
           "--server.port", "8501",
           "--server.address", "0.0.0.0",
           "--server.headless", "true"]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        logger.info("Dashboard stopped.")


if __name__ == "__main__":
    if "--bot" in sys.argv:
        run_scheduler_only()
    else:
        run_with_dashboard()
