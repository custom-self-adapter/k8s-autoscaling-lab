import logging
from datetime import datetime, timezone
from typing import override

from locust import HttpUser, LoadTestShape, events, task

from extract_prom import extract

CA_PATH = "./vagrant-kubeadm-kubernetes/certs/rootCA.crt"

slo_ms = 1000
request_logger = logging.getLogger("on_request")


def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")


class StatsStore:
    def __init__(self) -> None:
        self.response_time = []
        self.response_size = []
        self.response_code = []
    
    def reset(self):
        self.response_time = []
        self.response_size = []
        self.response_code = []


stats = StatsStore()


class WebsiteUser(HttpUser):
    @override
    def on_start(self) -> None:
        super().on_start()
        self.client.verify = CA_PATH

    @task
    def news(self):
        _ = self.client.get("/news.php")


class DoubleWave(LoadTestShape):
    user_count = []
    logger = logging.getLogger()

    stages: list[dict[str, int]] = [
        {"end": 30, "users": 20, "spawn_rate": 20},
        {"end": 120, "users": 240, "spawn_rate": 5},
        {"end": 180, "users": 120, "spawn_rate": 5},
        {"end": 240, "users": 240, "spawn_rate": 25},
        {"end": 300, "users": 20, "spawn_rate": 25},
    ]

    @override
    def reset_time(self):
        super().reset_time()
        self.user_count = []
        stats.reset()

    @override
    def tick(self):
        run_time = self.get_run_time()
        self.logger.info(
            f"run_time: {run_time}; user_count: {self.get_current_user_count()}"
        )

        for stage in self.stages:
            if run_time < stage["end"]:
                self.user_count.append(
                    {
                        "ts": get_timestamp(),
                        "value": self.get_current_user_count(),
                        "series": "user_count",
                    }
                )
                tick_data = (stage["users"], stage["spawn_rate"])
                return tick_data

        extract(
            user_count=self.user_count,
            response_time=stats.response_time,
            response_size=stats.response_size,
            response_code=stats.response_code
        )
        return None


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats.reset()


@events.request.add_listener
def on_request(
    request_type, name, response_time, response_length, response, exception, context, **kwargs
):
    """
    Register the response_time for each request
    """
    timestamp = get_timestamp()
    stats.response_time.append(
        {"ts": timestamp, "series": "response_time", "value": response_time}
    )
    stats.response_size.append(
        {"ts": timestamp, "series": "response_size", "value": response_length}
    )
    stats.response_code.append(
        {"ts": timestamp, "series": "response_code", "value": response.status_code}
    )


@events.report_to_master.add_listener
def on_report_to_master(client_id, data):
    """
    Worker instance reports their response_time to master
    """
    data["response_time"] = stats.response_time
    data["response_size"] = stats.response_size
    data["response_code"] = stats.response_code
    stats.response_time = []
    stats.response_size = []
    stats.response_code = []


@events.worker_report.add_listener
def on_worker_report(client_id, data):
    """
    Master collects response_time from workers
    """
    stats.response_time.extend(data["response_time"])
    stats.response_size.extend(data["response_size"])
    stats.response_code.extend(data["response_code"])
