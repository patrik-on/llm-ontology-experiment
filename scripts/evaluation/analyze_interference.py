from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


MODELS = ("baseline_qwen25_coder_7b", "b2_testing_v2", "b2_refactoring_v2", "b1_shared_v2")
TESTING_METRIC = "avg_test_quality_score"
REFACTORING_METRIC = "avg_refactoring_quality_score"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def by_model(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["model_name"]): item for item in items}


def score(value: float) -> str:
    return f"{value:.2f}"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def latex_pct(value: float) -> str:
    return f"{value:.2f}\\%"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def latex_escape(text: str) -> str:
    return text.replace("_", r"\_")


def build_analysis(evaluation_root: Path) -> dict[str, Any]:
    testing_items = by_model(read_json(evaluation_root / "metrics" / "testing" / "aggregate_metrics.json"))
    refactoring_items = by_model(read_json(evaluation_root / "metrics" / "refactoring" / "aggregate_metrics.json"))

    missing = [model for model in MODELS if model not in testing_items or model not in refactoring_items]
    if missing:
        raise ValueError(f"Missing required model(s) in aggregate metrics: {', '.join(missing)}")

    cross_task_scores: list[dict[str, Any]] = []
    for model in MODELS:
        cross_task_scores.append(
            {
                "model_name": model,
                "testing_score": float(testing_items[model][TESTING_METRIC]),
                "refactoring_score": float(refactoring_items[model][REFACTORING_METRIC]),
            }
        )

    scores = {row["model_name"]: row for row in cross_task_scores}
    testing_specialized_advantage = scores["b2_testing_v2"]["testing_score"] - scores["b1_shared_v2"]["testing_score"]
    refactoring_specialized_advantage = (
        scores["b2_refactoring_v2"]["refactoring_score"] - scores["b1_shared_v2"]["refactoring_score"]
    )
    testing_cross_task_gap = scores["b2_testing_v2"]["testing_score"] - scores["b2_testing_v2"]["refactoring_score"]
    refactoring_cross_task_gap = (
        scores["b2_refactoring_v2"]["refactoring_score"] - scores["b2_refactoring_v2"]["testing_score"]
    )
    shared_balance_gap = abs(scores["b1_shared_v2"]["testing_score"] - scores["b1_shared_v2"]["refactoring_score"])
    baseline_gap = scores["baseline_qwen25_coder_7b"]["testing_score"] - scores["baseline_qwen25_coder_7b"]["refactoring_score"]
    testing_interference = scores["b1_shared_v2"]["testing_score"] - scores["b2_testing_v2"]["testing_score"]
    refactoring_interference = (
        scores["b1_shared_v2"]["refactoring_score"] - scores["b2_refactoring_v2"]["refactoring_score"]
    )
    testing_interference_pct = 100.0 * testing_interference / scores["b2_testing_v2"]["testing_score"]
    refactoring_interference_pct = 100.0 * refactoring_interference / scores["b2_refactoring_v2"]["refactoring_score"]

    return {
        "evaluation_root": str(evaluation_root),
        "limit": int(testing_items[MODELS[0]].get("count", 0)),
        "models": list(MODELS),
        "metrics": {"testing": TESTING_METRIC, "refactoring": REFACTORING_METRIC},
        "cross_task_scores": cross_task_scores,
        "specialized_advantages": {
            "testing_specialized_advantage": testing_specialized_advantage,
            "refactoring_specialized_advantage": refactoring_specialized_advantage,
        },
        "cross_task_gaps": {
            "testing_cross_task_gap": testing_cross_task_gap,
            "refactoring_cross_task_gap": refactoring_cross_task_gap,
            "shared_balance_gap": shared_balance_gap,
            "baseline_testing_score": scores["baseline_qwen25_coder_7b"]["testing_score"],
            "baseline_refactoring_score": scores["baseline_qwen25_coder_7b"]["refactoring_score"],
            "baseline_gap_testing_minus_refactoring": baseline_gap,
            "baseline_gap_absolute": abs(baseline_gap),
        },
        "interference": {
            "testing_interference": testing_interference,
            "refactoring_interference": refactoring_interference,
            "testing_interference_pct": testing_interference_pct,
            "refactoring_interference_pct": refactoring_interference_pct,
        },
    }


def report_markdown(analysis: dict[str, Any]) -> str:
    scores = {row["model_name"]: row for row in analysis["cross_task_scores"]}
    interference = analysis["interference"]
    advantages = analysis["specialized_advantages"]

    score_rows = [
        [row["model_name"], score(row["testing_score"]), score(row["refactoring_score"])]
        for row in analysis["cross_task_scores"]
    ]
    interference_rows = [
        [
            "Testing",
            score(scores["b1_shared_v2"]["testing_score"]),
            score(scores["b2_testing_v2"]["testing_score"]),
            score(interference["testing_interference"]),
            pct(interference["testing_interference_pct"]),
        ],
        [
            "Refactoring",
            score(scores["b1_shared_v2"]["refactoring_score"]),
            score(scores["b2_refactoring_v2"]["refactoring_score"]),
            score(interference["refactoring_interference"]),
            pct(interference["refactoring_interference_pct"]),
        ],
    ]

    lines = [
        "# Interference and Cross-task Analysis",
        "",
        "## Data source",
        "",
        f"- Evaluation root: `{analysis['evaluation_root']}`",
        f"- Limit: {analysis['limit']}",
        "- Models: " + ", ".join(f"`{model}`" for model in analysis["models"]),
        f"- Testing metric: `{analysis['metrics']['testing']}`",
        f"- Refactoring metric: `{analysis['metrics']['refactoring']}`",
        "",
        "## Cross-task scores",
        "",
        markdown_table(["Model", "Testing score", "Refactoring score"], score_rows),
        "",
        "## Specialized vs shared comparison",
        "",
        "B2-T v2 is the testing-specialized model, B2-R v2 is the refactoring-specialized model, "
        "and B1 shared v2 is the multi-domain model trained on both tasks.",
        "",
        f"- Testing specialized advantage: {score(advantages['testing_specialized_advantage'])}.",
        f"- Refactoring specialized advantage: {score(advantages['refactoring_specialized_advantage'])}.",
        "",
        "## Interference metrics",
        "",
        markdown_table(
            ["Task", "Shared score", "Specialized score", "Difference", "Relative difference"],
            interference_rows,
        ),
        "",
        "A value close to zero indicates minimal interference. A negative value means that the shared model "
        "underperforms the corresponding specialized model, while a positive value means that the shared model "
        "outperforms the specialized model.",
        "",
        "## Interpretation",
        "",
        "On the testing task, the difference between the shared and specialized model is minimal. "
        "The shared B1 model reaches nearly the same testing score as the testing-specialized B2-T model, "
        "which suggests that multi-domain fine-tuning does not introduce substantial negative interference "
        "for test generation under the current proxy metric.",
        "",
        "On the refactoring task, the shared model trails the refactoring-specialized B2-R model more clearly. "
        "This indicates that specialization remains more beneficial for refactoring than for testing in the "
        "current setup. The cross-task scores also show task specialization: the testing model is weaker on "
        "refactoring, and the refactoring model is weaker on testing.",
        "",
        "Overall, the results suggest limited interference for testing and a moderate specialization advantage "
        "for refactoring. These findings should be interpreted as proxy-metric evidence rather than final "
        "semantic validation of generated tests or refactorings.",
        "",
        "## Limitations",
        "",
        "- The evaluation uses limit 50 rather than the full test splits.",
        "- The reported scores are proxy metrics.",
        "- The baseline uses the same prompt format as the fine-tuned models.",
        "- An executable JaCoCo subset is not yet included.",
        "- LoRA representation analysis is not yet included.",
        "",
    ]
    return "\n".join(lines)


def latex_tables(analysis: dict[str, Any]) -> str:
    scores = {row["model_name"]: row for row in analysis["cross_task_scores"]}
    interference = analysis["interference"]
    advantages = analysis["specialized_advantages"]
    gaps = analysis["cross_task_gaps"]

    cross_rows = "\n".join(
        f"{latex_escape(row['model_name'])} & {score(row['testing_score'])} & {score(row['refactoring_score'])} \\\\"
        for row in analysis["cross_task_scores"]
    )
    interference_rows = "\n".join(
        [
            (
                "Testing & "
                f"{score(scores['b1_shared_v2']['testing_score'])} & "
                f"{score(scores['b2_testing_v2']['testing_score'])} & "
                f"{score(interference['testing_interference'])} & "
                f"{latex_pct(interference['testing_interference_pct'])} \\\\"
            ),
            (
                "Refactoring & "
                f"{score(scores['b1_shared_v2']['refactoring_score'])} & "
                f"{score(scores['b2_refactoring_v2']['refactoring_score'])} & "
                f"{score(interference['refactoring_interference'])} & "
                f"{latex_pct(interference['refactoring_interference_pct'])} \\\\"
            ),
        ]
    )
    advantage_rows = "\n".join(
        [
            f"Testing specialized advantage & {score(advantages['testing_specialized_advantage'])} \\\\",
            f"Refactoring specialized advantage & {score(advantages['refactoring_specialized_advantage'])} \\\\",
            f"Testing cross-task gap & {score(gaps['testing_cross_task_gap'])} \\\\",
            f"Refactoring cross-task gap & {score(gaps['refactoring_cross_task_gap'])} \\\\",
            f"Shared balance gap & {score(gaps['shared_balance_gap'])} \\\\",
        ]
    )

    return "\n\n".join(
        [
            "\\begin{table}[h]\n"
            "\\centering\n"
            "\\begin{tabular}{lrr}\n"
            "\\hline\n"
            "Model & Testing & Refactoring \\\\\n"
            "\\hline\n"
            f"{cross_rows}\n"
            "\\hline\n"
            "\\end{tabular}\n"
            "\\caption{Cross-task proxy scores for baseline, specialized, and shared v2 models.}\n"
            "\\label{tab:v2-cross-task-scores}\n"
            "\\end{table}",
            "\\begin{table}[h]\n"
            "\\centering\n"
            "\\begin{tabular}{lrrrr}\n"
            "\\hline\n"
            "Task & Shared & Specialized & Difference & Relative diff. \\\\\n"
            "\\hline\n"
            f"{interference_rows}\n"
            "\\hline\n"
            "\\end{tabular}\n"
            "\\caption{Interference metrics comparing the shared v2 model with task-specialized v2 models.}\n"
            "\\label{tab:v2-interference}\n"
            "\\end{table}",
            "\\begin{table}[h]\n"
            "\\centering\n"
            "\\begin{tabular}{lr}\n"
            "\\hline\n"
            "Metric & Value \\\\\n"
            "\\hline\n"
            f"{advantage_rows}\n"
            "\\hline\n"
            "\\end{tabular}\n"
            "\\caption{Specialization and cross-task gap summary for v2 models.}\n"
            "\\label{tab:v2-specialization-gaps}\n"
            "\\end{table}",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze interference and cross-task behavior from aggregate metrics.")
    parser.add_argument("--evaluation-root", default="evaluation_v2_only")
    parser.add_argument("--output-dir", default="evaluation_v2_only/analysis")
    args = parser.parse_args()

    evaluation_root = Path(args.evaluation_root)
    output_dir = Path(args.output_dir)
    analysis = build_analysis(evaluation_root)

    cross_task_rows = analysis["cross_task_scores"]
    write_csv(output_dir / "cross_task_scores.csv", cross_task_rows, ["model_name", "testing_score", "refactoring_score"])

    interference = analysis["interference"]
    advantages = analysis["specialized_advantages"]
    gaps = analysis["cross_task_gaps"]
    summary_rows = [
        {"metric": key, "value": value}
        for group in (advantages, gaps, interference)
        for key, value in group.items()
    ]
    write_csv(output_dir / "interference_summary.csv", summary_rows, ["metric", "value"])
    write_json(output_dir / "interference_summary.json", analysis)
    (output_dir / "interference_report.md").write_text(report_markdown(analysis), encoding="utf-8")
    (output_dir / "latex_tables.tex").write_text(latex_tables(analysis), encoding="utf-8")

    print("Interference analysis written to:", output_dir)
    for row in cross_task_rows:
        print(f"{row['model_name']}: testing={row['testing_score']:.2f}, refactoring={row['refactoring_score']:.2f}")
    print(f"testing_interference={interference['testing_interference']:.2f} ({interference['testing_interference_pct']:.2f}%)")
    print(
        f"refactoring_interference={interference['refactoring_interference']:.2f} "
        f"({interference['refactoring_interference_pct']:.2f}%)"
    )


if __name__ == "__main__":
    main()
