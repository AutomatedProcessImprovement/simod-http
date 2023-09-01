import logging
import os
import time

import schedule

from simod_http.worker import clean_expired_discovery_results, mark_expired_discoveries

discovery_results_cleaning_interval = int(os.getenv("SIMOD_STORAGE_CLEANING_TIMEDELTA", 60 * 60 * 24))
discovery_expiration_timedelta = int(os.getenv("SIMOD_STORAGE_DISCOVERY_EXPIRATION_TIMEDELTA", 60 * 60 * 24 * 7))


schedule.every(discovery_expiration_timedelta).seconds.do(mark_expired_discoveries.delay)
schedule.every(discovery_results_cleaning_interval).seconds.do(clean_expired_discovery_results.delay)


def run_scheduler():
    logging.info("Running scheduler")
    logging.info(f"Discovery expiration timedelta: {discovery_expiration_timedelta}")
    logging.info(f"Discovery results cleaning interval: {discovery_results_cleaning_interval}")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    run_scheduler()
