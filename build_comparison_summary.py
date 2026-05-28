import argparse
from pathlib import Path

import pandas as pd

from plot_comparison_common import COMPARISON_METRICS, SCENARIO_LABELS
from plot_helper import compute_run_metrics, discover_result_files, summarize_runs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera os CSVs compartilhados de metricas por execucao e agregados "
            "a partir dos arquivos <run>_<sequencial>_<cenario>.csv."
        )
    )
    parser.add_argument(
        "--results-dir",
        default="tests/results",
        help="Diretorio com os CSVs de resultados brutos.",
    )
    parser.add_argument(
        "--summary-csv",
        default="tests/results/compare_summary.csv",
        help="Arquivo CSV com os agregados por cenario e metrica.",
    )
    parser.add_argument(
        "--runs-csv",
        default="tests/results/compare_runs.csv",
        help="Arquivo CSV com as metricas por execucao.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    results_dir = Path(args.results_dir)
    summary_path = Path(args.summary_csv)
    runs_path = Path(args.runs_csv)

    discovered = discover_result_files(results_dir, SCENARIO_LABELS)
    run_rows = [compute_run_metrics(row) for _, row in discovered.iterrows()]
    run_df = pd.DataFrame(run_rows).sort_values(["order", "run", "scenario"])
    summary_df = summarize_runs(run_df, COMPARISON_METRICS)

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_path, index=False)
    run_df.to_csv(runs_path, index=False)

    print(f"Arquivos analisados: {len(run_df)}")
    print(f"Resumo salvo em: {summary_path}")
    print(f"Execucoes salvas em: {runs_path}")


if __name__ == "__main__":
    main()
