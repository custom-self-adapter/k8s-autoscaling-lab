from plot_helper import MetricSpec

CONFIGURATION_LABELS = {
    "base_1": "Base 1 Repl",
    "base_5": "Base 5 Repl",
    "hpa_std": "HPA Std",
    "hpa_fast": "HPA Fast",
    "csa_h": "CSA H",
    "csa_hq_25": "CSA HQ 25",
    "csa_hq_50": "CSA HQ 50",
    "base_1500": "Base 1 Repl 1.5 CPU",
    "vpa": "VPA",
    "csa_v": "CSA V",
    "csa_vq": "CSA VQ",
}

COMPARISON_METRICS = [
    MetricSpec("pods_mean", "Media de Pods (número de réplicas)"),
    MetricSpec("cpu_limits_mean", "Média do limite de CPU (fração de CPU)"),
    MetricSpec("response_time_mean", "Tempo medio das respostas (ms)"),
    MetricSpec("response_size_mean", "Tamanho medio das respostas (bytes)"),
    MetricSpec("success_rate", "Respostas bem-sucedidas (%)", percent_axis=True),
    MetricSpec(
        "slo_breach_success_rate",
        "Requisicoes acima do SLO, apenas sucesso (%)",
        percent_axis=True,
    ),
]


