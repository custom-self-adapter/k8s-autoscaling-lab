import logging
from typing import override
from locust import HttpUser, task, LoadTestShape
from datetime import datetime, timezone

from extract_prom import extract

CA_PATH = "./vagrant-kubeadm-kubernetes/certs/rootCA.crt"


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
        # {"end": 30, "users": 20, "spawn_rate": 20},
        # {"end": 150, "users": 200, "spawn_rate": 5},
        # {"end": 180, "users": 100, "spawn_rate": 5},
        # {"end": 270, "users": 200, "spawn_rate": 20},
        # {"end": 300, "users": 20, "spawn_rate": 90},
    ]

    @override
    def reset_time(self):
        super().reset_time()
        self.user_count = []

    @override
    def tick(self):
        run_time = self.get_run_time()
        self.logger.info(f"run_time: {run_time}; user_count: {self.get_current_user_count()}")

        for stage in self.stages:
            if run_time < stage["end"]:
                self.user_count.append(
                    {
                        "ts": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%d %H:%M:%S%z"
                        ),
                        "value": self.get_current_user_count(),
                        "series": "user_count",
                    }
                )
                tick_data = (stage["users"], stage["spawn_rate"])
                return tick_data

        extract(self.user_count)
        return None
