"""Long-running in-process scheduler. Start with:  python backend/scheduler.py  (from the project root)

Schedules come from .env (cron syntax: minute hour day month day-of-week; use day NAMES like fri):
  WEEKLY_CRON    default "0 9 * * fri"      -> weekly report draft
  REMINDER_CRON  default "0 9 * * mon-fri"  -> overdue/blocked reminders
  SCHEDULER_TZ   default "UTC"              -> e.g. "Asia/Kolkata", "Europe/London"
  SCHEDULE_SEND  default "false"            -> "true" to really send email/Slack
Closure is a one-off decision, so it is not scheduled; run it manually when the project ends.
"""
import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()
from run_scheduled import run_job

log = logging.getLogger("scheduler")
SEND = os.getenv("SCHEDULE_SEND", "false").lower() == "true"
TZ = os.getenv("SCHEDULER_TZ", "UTC")


def safe(job):
    def _run():
        try:
            run_job(job, send=SEND)
        except Exception:
            log.exception("Job '%s' failed (will retry at next scheduled time)", job)
    return _run


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sched = BlockingScheduler(timezone=TZ)
    jobs = {"weekly": os.getenv("WEEKLY_CRON", "0 9 * * fri"),
            "reminders": os.getenv("REMINDER_CRON", "0 9 * * mon-fri")}
    for name, cron in jobs.items():
        sched.add_job(safe(name), CronTrigger.from_crontab(cron, timezone=TZ), id=name,
                      coalesce=True, misfire_grace_time=3600, max_instances=1)
        log.info("Scheduled '%s' at '%s' (%s), send=%s", name, cron, TZ, SEND)
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped")


if __name__ == "__main__":
    main()
