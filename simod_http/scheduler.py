import time

import schedule

from simod_http.main import api
from simod_http.worker import clean_expired_discovery_results

discovery_results_cleaning_interval = api.state.app.configuration.storage.cleaning_timedelta


def clean_storage() -> dict:
    return clean_expired_discovery_results.delay()


schedule.every(discovery_results_cleaning_interval).seconds.do(clean_storage)


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_scheduler()
