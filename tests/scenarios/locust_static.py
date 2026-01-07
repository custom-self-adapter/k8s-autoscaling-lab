
from typing import override
from locust import HttpUser, task


CA_PATH = "./vagrant-kubeadm-kubernetes/certs/rootCA.crt"


class WebsiteUser(HttpUser):
    @override
    def on_start(self) -> None:
        super().on_start()
        self.client.verify = CA_PATH
    
    @task
    def news(self):
        _ = self.client.get("/news.php")
