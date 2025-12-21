import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import override

from locust import HttpUser, LoadTestShape, events, task

from extract_prom import extract

CA_PATH = "./vagrant-kubeadm-kubernetes/certs/rootCA.crt"

slo_ms = 1000
request_logger = logging.getLogger("on_request")


def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")


@dataclass(frozen=True)
class Stats:
    ts: str
    response_time: float
    response_length: int
    status_code: int

    @staticmethod
    def from_dict(row: dict):
        try:
            return Stats(
                ts=row["ts"],
                response_time=float(row["response_time"]),
                response_length=int(row["response_length"]),
                status_code=int(row["status_code"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def as_response_time_row(self) -> dict:
        return {
            "ts": self.ts,
            "series": "response_time",
            "value": self.response_time,
            "response_size": self.response_length,
            "status_code": self.status_code,
        }

    def key(self) -> tuple:
        return (self.ts, self.response_time, self.response_length, self.status_code)


class StatsStore:
    def __init__(self) -> None:
        self._entries: dict[tuple, Stats] = {}

    def reset(self):
        self._entries.clear()

    def add_request(
        self,
        timestamp: str,
        response_time: float,
        response_length: int,
        status_code: int,
    ):
        try:
            entry = Stats(
                ts=timestamp,
                response_time=float(response_time),
                response_length=int(response_length),
                status_code=int(status_code),
            )
        except (TypeError, ValueError):
            return
        self._entries[entry.key()] = entry

    def extend_entries(self, rows: list[dict]):
        for row in rows or []:
            entry = Stats.from_dict(row)
            if entry is None:
                continue
            self._entries[entry.key()] = entry

    def get_entries(self, consume: bool = False):
        rows = [
            {
                "ts": s.ts,
                "response_time": s.response_time,
                "response_length": s.response_length,
                "status_code": s.status_code,
            }
            for s in self._entries.values()
        ]
        if consume:
            self._entries.clear()
        return rows

    def get_response_time_rows(self):
        return [s.as_response_time_row() for s in self._entries.values()]


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
        {"end": 120, "users": 250, "spawn_rate": 5},
        {"end": 180, "users": 100, "spawn_rate": 5},
        {"end": 240, "users": 250, "spawn_rate": 25},
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
            response_time=stats.get_response_time_rows()
        )
        return None


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats.reset()


@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    response,
    exception,
    context,
    **kwargs,
):
    """
    Register the response_time for each request
    """
    timestamp = get_timestamp()
    stats.add_request(timestamp, response_time, response_length, response.status_code)


@events.report_to_master.add_listener
def on_report_to_master(client_id, data):
    """
    Worker instance reports their response_time to master
    """
    data["responses"] = stats.get_entries(consume=True)


@events.worker_report.add_listener
def on_worker_report(client_id, data):
    """
    Master collects response_time from workers
    """
    stats.extend_entries(data.get("responses", []))
