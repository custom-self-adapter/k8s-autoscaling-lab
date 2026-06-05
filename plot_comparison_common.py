from plot_helper import MetricSpec

CONFIGURATION_LABELS = {
    "base_1": "1 Replica",
    "base_5": "5 Replicas",
    "base_1000": "1 Replica 1 CPU",
    "hpa_std": "HPA Std",
    "hpa_fast": "HPA Fast",
    "csa_h": "CSA H",
    "csa_hq_25": "CSA HQ 25",
    "csa_hq_50": "CSA HQ 50",
    "base_1500": "Base 1500",
    "vpa": "VPA",
    "csa_v": "CSA V",
    "csa_vq": "CSA VQ",
}

COMPARISON_METRICS = [
    MetricSpec("pods_mean", "Media de Pods (número de réplicas)"),
    MetricSpec("cpu_limits_mean", "Média do limite de CPU (fração de CPU)"),
    MetricSpec("response_time_mean", "Tempo medio das respostas (ms)"),
    MetricSpec("response_size_mean", "Tamanho medio das respostas (bytes)"),
    MetricSpec("success_rate", "Respostas 200 (%)", percent_axis=True),
    MetricSpec(
        "slo_breach_success_rate",
        "Requisicoes acima do SLO, apenas sucesso (%)",
        percent_axis=True,
    ),
]
