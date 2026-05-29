from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

import torch


MODEL_ORDER = ("b2_testing_v2", "b2_refactoring_v2", "b1_shared_v2")
PAIR_ORDER = (
    ("b2_testing_v2", "b2_refactoring_v2"),
    ("b1_shared_v2", "b2_testing_v2"),
    ("b1_shared_v2", "b2_refactoring_v2"),
)
MODULE_TYPES = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")


def load_safetensors(path: Path) -> dict[str, torch.Tensor]:
    try:
        from safetensors.torch import load_file
    except ImportError as exc:
        raise SystemExit("Missing dependency 'safetensors'. Install it in the active environment.") from exc
    return load_file(path, device="cpu")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
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


def tensor_prefix(key: str, marker: str) -> str:
    return key.split(f".{marker}", 1)[0] if f".{marker}" in key else key.split(marker, 1)[0].rstrip(".")


def parse_layer_index(prefix: str) -> int:
    match = re.search(r"(?:layers|h|blocks)\.(\d+)", prefix)
    return int(match.group(1)) if match else -1


def parse_module_name(prefix: str) -> str:
    for module_type in MODULE_TYPES:
        if re.search(rf"(?:^|\.){re.escape(module_type)}(?:\.|$)", prefix):
            return module_type
    parts = [part for part in prefix.split(".") if part]
    return parts[-1] if parts else "unknown"


def canonical_module_key(prefix: str) -> str:
    layer_index = parse_layer_index(prefix)
    module_name = parse_module_name(prefix)
    if layer_index >= 0:
        return f"layers.{layer_index}.{module_name}"
    return f"unknown.{module_name}.{prefix}"


def collect_modules(adapter_dir: Path) -> dict[str, dict[str, Any]]:
    tensors = load_safetensors(adapter_dir / "adapter_model.safetensors")
    modules: dict[str, dict[str, Any]] = {}
    for key, tensor in tensors.items():
        if "lora_A" not in key and "lora_B" not in key:
            continue
        marker = "lora_A" if "lora_A" in key else "lora_B"
        prefix = tensor_prefix(key, marker)
        module_key = canonical_module_key(prefix)
        item = modules.setdefault(
            module_key,
            {
                "tensor_key_prefix": prefix,
                "layer_index": parse_layer_index(prefix),
                "module_name": parse_module_name(prefix),
            },
        )
        item["A" if marker == "lora_A" else "B"] = tensor.float()
        item["A_key" if marker == "lora_A" else "B_key"] = key
    return modules


def fro_norm(tensor: torch.Tensor) -> float:
    return float(torch.linalg.vector_norm(tensor).item())


def delta_tensor(module: dict[str, Any]) -> torch.Tensor | None:
    a = module.get("A")
    b = module.get("B")
    if not isinstance(a, torch.Tensor) or not isinstance(b, torch.Tensor):
        return None
    if a.ndim != 2 or b.ndim != 2 or b.shape[1] != a.shape[0]:
        return None
    return b @ a


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    a_flat = a.flatten().float()
    b_flat = b.flatten().float()
    denom = torch.linalg.vector_norm(a_flat) * torch.linalg.vector_norm(b_flat)
    if float(denom.item()) == 0.0:
        return 0.0
    return float(torch.dot(a_flat, b_flat).item() / denom.item())


def l2_distance(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(torch.linalg.vector_norm(a.flatten().float() - b.flatten().float()).item())


def fallback_vector(module: dict[str, Any]) -> torch.Tensor | None:
    a = module.get("A")
    b = module.get("B")
    if not isinstance(a, torch.Tensor) or not isinstance(b, torch.Tensor):
        return None
    return torch.cat([a.flatten().float(), b.flatten().float()])


def module_norm_rows(model_name: str, modules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module_key, module in sorted(modules.items(), key=lambda item: (item[1]["layer_index"], item[1]["module_name"])):
        a = module.get("A")
        b = module.get("B")
        if not isinstance(a, torch.Tensor) or not isinstance(b, torch.Tensor):
            continue
        a_norm = fro_norm(a)
        b_norm = fro_norm(b)
        delta = delta_tensor(module)
        rows.append(
            {
                "model_name": model_name,
                "layer_index": module["layer_index"],
                "module_name": module["module_name"],
                "module_key": module_key,
                "tensor_key_prefix": module["tensor_key_prefix"],
                "lora_A_norm": a_norm,
                "lora_B_norm": b_norm,
                "proxy_fro_norm": a_norm * b_norm,
                "delta_fro_norm": fro_norm(delta) if delta is not None else "",
                "num_params_A": int(a.numel()),
                "num_params_B": int(b.numel()),
            }
        )
    return rows


def layer_norm_rows(module_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_layer: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in module_rows:
        by_layer[int(row["layer_index"])][str(row["model_name"])].append(float(row["proxy_fro_norm"]))

    rows: list[dict[str, Any]] = []
    for layer_index in sorted(layer for layer in by_layer if layer >= 0):
        row: dict[str, Any] = {"layer_index": layer_index}
        for model_name in MODEL_ORDER:
            values = by_layer[layer_index].get(model_name, [])
            row[f"{model_name}_norm"] = sum(values)
            row[f"{model_name}_mean_norm"] = mean(values) if values else 0.0
            row[f"{model_name}_max_norm"] = max(values) if values else 0.0
            row[f"{model_name}_module_count"] = len(values)
        rows.append(row)
    return rows


def pairwise_rows(modules_by_model: dict[str, dict[str, dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    module_rows: list[dict[str, Any]] = []
    for left, right in PAIR_ORDER:
        common_keys = sorted(set(modules_by_model[left]) & set(modules_by_model[right]))
        for module_key in common_keys:
            left_module = modules_by_model[left][module_key]
            right_module = modules_by_model[right][module_key]
            left_delta = delta_tensor(left_module)
            right_delta = delta_tensor(right_module)
            method = "delta"
            if left_delta is None or right_delta is None or left_delta.shape != right_delta.shape:
                left_delta = fallback_vector(left_module)
                right_delta = fallback_vector(right_module)
                method = "concat_A_B"
            if left_delta is None or right_delta is None or left_delta.shape != right_delta.shape:
                continue
            left_norm = fro_norm(left_delta)
            right_norm = fro_norm(right_delta)
            module_rows.append(
                {
                    "left_model": left,
                    "right_model": right,
                    "pair": f"{left}__{right}",
                    "layer_index": left_module["layer_index"],
                    "module_name": left_module["module_name"],
                    "module_key": module_key,
                    "cosine_similarity": cosine(left_delta, right_delta),
                    "l2_distance": l2_distance(left_delta, right_delta),
                    "left_norm": left_norm,
                    "right_norm": right_norm,
                    "norm_ratio_left_over_right": left_norm / right_norm if right_norm else math.inf,
                    "comparison_method": method,
                }
            )

    summary_rows: list[dict[str, Any]] = []
    for left, right in PAIR_ORDER:
        rows = [row for row in module_rows if row["left_model"] == left and row["right_model"] == right]
        cosines = [float(row["cosine_similarity"]) for row in rows]
        distances = [float(row["l2_distance"]) for row in rows]
        summary_rows.append(
            {
                "left_model": left,
                "right_model": right,
                "pair": f"{left}__{right}",
                "common_module_count": len(rows),
                "mean_cosine_similarity": mean(cosines) if cosines else 0.0,
                "median_cosine_similarity": median(cosines) if cosines else 0.0,
                "mean_l2_distance": mean(distances) if distances else 0.0,
                "median_l2_distance": median(distances) if distances else 0.0,
            }
        )
    return module_rows, summary_rows


def aggregate_pairwise_by_layer(module_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in module_rows:
        grouped[(str(row["pair"]), int(row["layer_index"]))].append(row)
    rows = []
    for (pair, layer_index), items in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        cosines = [float(item["cosine_similarity"]) for item in items]
        distances = [float(item["l2_distance"]) for item in items]
        left, right = pair.split("__", 1)
        rows.append(
            {
                "pair": pair,
                "left_model": left,
                "right_model": right,
                "layer_index": layer_index,
                "module_count": len(items),
                "mean_cosine_similarity": mean(cosines),
                "median_cosine_similarity": median(cosines),
                "mean_l2_distance": mean(distances),
            }
        )
    return rows


def aggregate_pairwise_by_module_type(module_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in module_rows:
        grouped[(str(row["pair"]), str(row["module_name"]))].append(row)
    rows = []
    for (pair, module_name), items in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        cosines = [float(item["cosine_similarity"]) for item in items]
        distances = [float(item["l2_distance"]) for item in items]
        left, right = pair.split("__", 1)
        rows.append(
            {
                "pair": pair,
                "left_model": left,
                "right_model": right,
                "module_name": module_name,
                "module_count": len(items),
                "mean_cosine_similarity": mean(cosines),
                "median_cosine_similarity": median(cosines),
                "mean_l2_distance": mean(distances),
            }
        )
    return rows


def shared_similarity_rows(layer_pairwise: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pair_layer = {(row["pair"], int(row["layer_index"])): row for row in layer_pairwise}
    layers = sorted(
        {
            int(row["layer_index"])
            for row in layer_pairwise
            if row["pair"] in {"b1_shared_v2__b2_testing_v2", "b1_shared_v2__b2_refactoring_v2"}
        }
    )
    rows = []
    for layer_index in layers:
        testing = by_pair_layer.get(("b1_shared_v2__b2_testing_v2", layer_index))
        refactoring = by_pair_layer.get(("b1_shared_v2__b2_refactoring_v2", layer_index))
        if not testing or not refactoring:
            continue
        testing_cos = float(testing["mean_cosine_similarity"])
        refactoring_cos = float(refactoring["mean_cosine_similarity"])
        if abs(testing_cos - refactoring_cos) < 1e-12:
            closer = "tie"
        elif testing_cos > refactoring_cos:
            closer = "testing"
        else:
            closer = "refactoring"
        rows.append(
            {
                "layer_index": layer_index,
                "b1_to_testing_cosine": testing_cos,
                "b1_to_refactoring_cosine": refactoring_cos,
                "cosine_difference_testing_minus_refactoring": testing_cos - refactoring_cos,
                "shared_closer_to": closer,
            }
        )
    return rows


def top_layers(layer_rows: list[dict[str, Any]], model_name: str, limit: int = 5) -> list[dict[str, Any]]:
    key = f"{model_name}_norm"
    return sorted(
        ({"layer_index": row["layer_index"], "proxy_fro_norm_sum": row[key]} for row in layer_rows),
        key=lambda row: float(row["proxy_fro_norm_sum"]),
        reverse=True,
    )[:limit]


def summary_payload(
    adapter_paths: dict[str, Path],
    module_rows: list[dict[str, Any]],
    layer_rows: list[dict[str, Any]],
    pairwise_summary: list[dict[str, Any]],
    module_type_pairwise: list[dict[str, Any]],
    shared_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pair_by_name = {row["pair"]: row for row in pairwise_summary}
    b1_testing = pair_by_name["b1_shared_v2__b2_testing_v2"]["mean_cosine_similarity"]
    b1_refactoring = pair_by_name["b1_shared_v2__b2_refactoring_v2"]["mean_cosine_similarity"]
    if abs(b1_testing - b1_refactoring) < 1e-12:
        shared_closer = "tie"
    elif b1_testing > b1_refactoring:
        shared_closer = "testing"
    else:
        shared_closer = "refactoring"
    closer_counts = dict(defaultdict(int))
    for row in shared_rows:
        closer_counts[str(row["shared_closer_to"])] = closer_counts.get(str(row["shared_closer_to"]), 0) + 1
    return {
        "adapter_paths": {model: str(path) for model, path in adapter_paths.items()},
        "adapter_configs": {
            model: read_json(path / "adapter_config.json")
            for model, path in adapter_paths.items()
        },
        "module_count": len(module_rows),
        "top_layers": {model: top_layers(layer_rows, model) for model in MODEL_ORDER},
        "pairwise_similarity": pairwise_summary,
        "module_type_pairwise_similarity": module_type_pairwise,
        "shared_overall": {
            "b1_to_testing_mean_cosine": b1_testing,
            "b1_to_refactoring_mean_cosine": b1_refactoring,
            "shared_closer_to": shared_closer,
        },
        "shared_layer_closer_counts": closer_counts,
    }


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def fmt(value: Any) -> str:
    return f"{float(value):.4f}" if isinstance(value, (int, float)) else str(value)


def latex_escape(text: str) -> str:
    return text.replace("_", r"\_")


def report_markdown(summary: dict[str, Any], layer_rows: list[dict[str, Any]]) -> str:
    pair_rows = [
        [
            f"{row['left_model']} vs {row['right_model']}",
            str(row["common_module_count"]),
            fmt(row["mean_cosine_similarity"]),
            fmt(row["median_cosine_similarity"]),
            fmt(row["mean_l2_distance"]),
        ]
        for row in summary["pairwise_similarity"]
    ]
    top_rows: list[list[str]] = []
    for model in MODEL_ORDER:
        for item in summary["top_layers"][model]:
            top_rows.append([model, str(item["layer_index"]), fmt(item["proxy_fro_norm_sum"])])
    shared = summary["shared_overall"]
    top_sets = {
        model: {int(item["layer_index"]) for item in summary["top_layers"][model]}
        for model in MODEL_ORDER
    }
    all_overlap = sorted(set.intersection(*top_sets.values()))
    shared_testing_overlap = sorted(top_sets["b1_shared_v2"] & top_sets["b2_testing_v2"])
    shared_refactoring_overlap = sorted(top_sets["b1_shared_v2"] & top_sets["b2_refactoring_v2"])
    lines = [
        "# LoRA Adapter Analysis",
        "",
        "## Goal",
        "",
        "The goal is to analyze how the v2 LoRA adapters differ between the testing-specialized, "
        "refactoring-specialized, and shared fine-tuning settings without running model inference.",
        "",
        "## Data",
        "",
        *[f"- `{model}`: `{path}`" for model, path in summary["adapter_paths"].items()],
        "",
        "## Method",
        "",
        "LoRA tensors are paired by module prefix using their `lora_A` and `lora_B` weights. "
        "For compatible two-dimensional tensors, the LoRA update is approximated as `DeltaW = B @ A`. "
        "The script also records the proxy norm `||A||_F * ||B||_F`. Pairwise adapter similarity is measured "
        "as cosine similarity between corresponding flattened `DeltaW` matrices, falling back to concatenated "
        "`A` and `B` vectors if direct multiplication is not available.",
        "",
        "These measurements are representational proxies. They are not a direct mechanistic explanation of model behavior.",
        "",
        "## Layer norm analysis",
        "",
        markdown_table(["Model", "Layer", "Layer norm sum"], top_rows),
        "",
        "The top-layer table identifies where each adapter concentrates its largest LoRA proxy norms. "
        "Overlap between top layers suggests shared adaptation regions, while divergent top layers can indicate "
        "task-specific adaptation patterns.",
        "",
        f"Across all three adapters, the shared top-layer overlap is: {all_overlap or 'none'}. "
        f"B1 shared overlaps with B2-T in layers {shared_testing_overlap or 'none'} and with B2-R in layers "
        f"{shared_refactoring_overlap or 'none'}. This suggests that the shared adapter uses a mixture of "
        "testing-like and refactoring-like high-norm adaptation regions.",
        "",
        "## Pairwise adapter similarity",
        "",
        markdown_table(["Pair", "Common modules", "Mean cosine", "Median cosine", "Mean L2"], pair_rows),
        "",
        "## Shared adapter interpretation",
        "",
        f"Overall, B1 shared is closer to `{shared['shared_closer_to']}` by mean cosine similarity. "
        f"The B1-to-testing mean cosine is {fmt(shared['b1_to_testing_mean_cosine'])}, while the "
        f"B1-to-refactoring mean cosine is {fmt(shared['b1_to_refactoring_mean_cosine'])}.",
        "",
        f"Layer-level closer counts: {summary['shared_layer_closer_counts']}.",
        "",
        "## Interpretation",
        "",
        "If B2-T and B2-R have low similarity, this supports the presence of task-specific LoRA updates. "
        "If B1 shared is similar to both specialized adapters, it suggests compromise representations that combine "
        "information useful for both domains. Similar top layers across adapters may indicate common adaptation areas, "
        "whereas different top layers may indicate domain-specific adaptation areas.",
        "",
        "## Limitations",
        "",
        "- The analysis uses only LoRA weights, not model activations.",
        "- Attention heads are not analyzed directly.",
        "- Cosine similarity between weights is not identical to functional similarity.",
        "- Results should be interpreted together with performance metrics and qualitative analysis.",
        "",
    ]
    return "\n".join(lines)


def latex_tables(summary: dict[str, Any]) -> str:
    top_lines = []
    for model in MODEL_ORDER:
        for rank, item in enumerate(summary["top_layers"][model], 1):
            top_lines.append(
                f"{latex_escape(model)} & {rank} & {item['layer_index']} & {float(item['proxy_fro_norm_sum']):.4f} \\\\"
            )
    pair_lines = [
        (
            f"{latex_escape(row['left_model'])} vs {latex_escape(row['right_model'])} & "
            f"{row['common_module_count']} & {float(row['mean_cosine_similarity']):.4f} & "
            f"{float(row['median_cosine_similarity']):.4f} \\\\"
        )
        for row in summary["pairwise_similarity"]
    ]
    shared = summary["shared_overall"]
    shared_lines = [
        f"B1 shared vs B2-T & {float(shared['b1_to_testing_mean_cosine']):.4f} \\\\",
        f"B1 shared vs B2-R & {float(shared['b1_to_refactoring_mean_cosine']):.4f} \\\\",
        f"Closer adapter & \\multicolumn{{1}}{{l}}{{{shared['shared_closer_to']}}} \\\\",
    ]
    return "\n\n".join(
        [
            "\\begin{table}[h]\n"
            "\\centering\n"
            "\\begin{tabular}{lrrr}\n"
            "\\hline\n"
            "Model & Rank & Layer & Norm sum \\\\\n"
            "\\hline\n"
            + "\n".join(top_lines)
            + "\n\\hline\n"
            "\\end{tabular}\n"
            "\\caption{Top LoRA norm layer for each v2 adapter.}\n"
            "\\label{tab:lora-top-layers}\n"
            "\\end{table}",
            "\\begin{table}[h]\n"
            "\\centering\n"
            "\\begin{tabular}{lrrr}\n"
            "\\hline\n"
            "Adapter pair & Modules & Mean cosine & Median cosine \\\\\n"
            "\\hline\n"
            + "\n".join(pair_lines)
            + "\n\\hline\n"
            "\\end{tabular}\n"
            "\\caption{Pairwise LoRA adapter similarity for v2 models.}\n"
            "\\label{tab:lora-pairwise-similarity}\n"
            "\\end{table}",
            "\\begin{table}[h]\n"
            "\\centering\n"
            "\\begin{tabular}{lr}\n"
            "\\hline\n"
            "Comparison & Mean cosine \\\\\n"
            "\\hline\n"
            + "\n".join(shared_lines)
            + "\n\\hline\n"
            "\\end{tabular}\n"
            "\\caption{Shared adapter similarity summary.}\n"
            "\\label{tab:lora-shared-similarity}\n"
            "\\end{table}",
        ]
    ) + "\n"


def maybe_write_plots(output_dir: Path, layer_rows: list[dict[str, Any]], shared_rows: list[dict[str, Any]]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    for model in MODEL_ORDER:
        xs = [int(row["layer_index"]) for row in layer_rows]
        ys = [float(row[f"{model}_norm"]) for row in layer_rows]
        plt.figure(figsize=(8, 3))
        plt.plot(xs, ys, marker="o", linewidth=1)
        plt.xlabel("Layer")
        plt.ylabel("Proxy Frobenius norm sum")
        plt.title(model)
        plt.tight_layout()
        plt.savefig(output_dir / f"layer_norms_{model}.png", dpi=150)
        plt.close()
    if shared_rows:
        xs = [int(row["layer_index"]) for row in shared_rows]
        testing = [float(row["b1_to_testing_cosine"]) for row in shared_rows]
        refactoring = [float(row["b1_to_refactoring_cosine"]) for row in shared_rows]
        plt.figure(figsize=(8, 3))
        plt.plot(xs, testing, marker="o", linewidth=1, label="B1 vs B2-T")
        plt.plot(xs, refactoring, marker="o", linewidth=1, label="B1 vs B2-R")
        plt.xlabel("Layer")
        plt.ylabel("Mean cosine similarity")
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_dir / "shared_similarity_by_layer.png", dpi=150)
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze v2 LoRA adapter norms and pairwise similarities.")
    parser.add_argument("--b2-testing", required=True)
    parser.add_argument("--b2-refactoring", required=True)
    parser.add_argument("--b1-shared", required=True)
    parser.add_argument("--output-dir", default="evaluation_v2_only/lora_analysis")
    args = parser.parse_args()

    adapter_paths = {
        "b2_testing_v2": Path(args.b2_testing),
        "b2_refactoring_v2": Path(args.b2_refactoring),
        "b1_shared_v2": Path(args.b1_shared),
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    modules_by_model = {model: collect_modules(path) for model, path in adapter_paths.items()}
    module_rows = [row for model in MODEL_ORDER for row in module_norm_rows(model, modules_by_model[model])]
    layer_rows = layer_norm_rows(module_rows)
    module_pairwise_rows, pairwise_summary = pairwise_rows(modules_by_model)
    layer_pairwise_rows = aggregate_pairwise_by_layer(module_pairwise_rows)
    module_type_pairwise_rows = aggregate_pairwise_by_module_type(module_pairwise_rows)
    shared_rows = shared_similarity_rows(layer_pairwise_rows)
    summary = summary_payload(adapter_paths, module_rows, layer_rows, pairwise_summary, module_type_pairwise_rows, shared_rows)

    write_csv(
        output_dir / "module_lora_norms.csv",
        module_rows,
        [
            "model_name",
            "layer_index",
            "module_name",
            "module_key",
            "tensor_key_prefix",
            "lora_A_norm",
            "lora_B_norm",
            "proxy_fro_norm",
            "delta_fro_norm",
            "num_params_A",
            "num_params_B",
        ],
    )
    write_csv(output_dir / "layer_lora_norms.csv", layer_rows, list(layer_rows[0].keys()) if layer_rows else [])
    write_csv(
        output_dir / "adapter_pairwise_similarity.csv",
        pairwise_summary,
        [
            "left_model",
            "right_model",
            "pair",
            "common_module_count",
            "mean_cosine_similarity",
            "median_cosine_similarity",
            "mean_l2_distance",
            "median_l2_distance",
        ],
    )
    write_csv(
        output_dir / "layer_pairwise_similarity.csv",
        layer_pairwise_rows,
        [
            "pair",
            "left_model",
            "right_model",
            "layer_index",
            "module_count",
            "mean_cosine_similarity",
            "median_cosine_similarity",
            "mean_l2_distance",
        ],
    )
    write_csv(
        output_dir / "module_type_pairwise_similarity.csv",
        module_type_pairwise_rows,
        [
            "pair",
            "left_model",
            "right_model",
            "module_name",
            "module_count",
            "mean_cosine_similarity",
            "median_cosine_similarity",
            "mean_l2_distance",
        ],
    )
    write_csv(
        output_dir / "shared_similarity_by_layer.csv",
        shared_rows,
        [
            "layer_index",
            "b1_to_testing_cosine",
            "b1_to_refactoring_cosine",
            "cosine_difference_testing_minus_refactoring",
            "shared_closer_to",
        ],
    )
    write_json(output_dir / "lora_analysis_summary.json", summary)
    (output_dir / "lora_analysis_report.md").write_text(report_markdown(summary, layer_rows), encoding="utf-8")
    (output_dir / "latex_tables.tex").write_text(latex_tables(summary), encoding="utf-8")
    maybe_write_plots(output_dir, layer_rows, shared_rows)

    print("LoRA adapter analysis written to:", output_dir)
    for model in MODEL_ORDER:
        print(f"\nTop 5 layers for {model}:")
        for item in summary["top_layers"][model]:
            print(f"  layer {item['layer_index']}: {float(item['proxy_fro_norm_sum']):.4f}")
    print("\nPairwise cosine similarity:")
    for row in pairwise_summary:
        print(f"  {row['left_model']} vs {row['right_model']}: mean={float(row['mean_cosine_similarity']):.4f}")
    print(f"\nB1 shared is closer to: {summary['shared_overall']['shared_closer_to']}")


if __name__ == "__main__":
    main()
