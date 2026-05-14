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
    """
    logger.info("Starting internal scheduler...")
    
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
