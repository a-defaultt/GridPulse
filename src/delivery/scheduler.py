# src/delivery/scheduler.py
import time
import logging
import schedule
from src.main import run_pipeline

logger = logging.getLogger(__name__)

def run_scheduler():
    """
    Internal scheduler loop.
    Runs daily at 08:00 UTC, weekly on Mondays at 09:00 UTC, 
    and monthly on the 1st at 10:00 UTC.
    V6 Enhancement: Trigger a baseline run on startup.
    """
    logger.info("Starting internal scheduler...")
    
    # V6: Run on Startup baseline
    logger.info("Performing initial startup run (Edition: daily)...")
    try:
        from src.database.db_handler import get_last_sent_date
        from src.utils.datetime_utils import str_to_dt, utc_now
        from datetime import timedelta

        should_run = True
        last_sent_str = get_last_sent_date('daily')
        if last_sent_str:
            last_sent_dt = str_to_dt(last_sent_str)
            if last_sent_dt and (utc_now() - last_sent_dt < timedelta(hours=18)):
                logger.info(f"Daily newsletter was already sent recently (at {last_sent_str}). Skipping startup run.")
                should_run = False

        if should_run:
            run_pipeline(edition='daily')
            logger.info("Startup run completed successfully.")
    except Exception as e:
        logger.error(f"Startup run failed: {e}")

    # Schedule Daily
    schedule.every().day.at("08:00").do(run_pipeline, edition='daily')
    
    # Schedule Weekly
    schedule.every().monday.at("09:00").do(run_pipeline, edition='weekly')
    
    # Schedule Monthly
    # schedule doesn't have a direct '1st of month', so we use a check
    def monthly_job():
        import datetime
        if datetime.datetime.now().day == 1:
            run_pipeline(edition='monthly')
            
    schedule.every().day.at("10:00").do(monthly_job)
    
    logger.info("Scheduler initialized. Waiting for jobs...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # For testing the scheduler directly
    logging.basicConfig(level=logging.INFO)
    run_scheduler()
