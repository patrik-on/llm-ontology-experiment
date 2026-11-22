"""Compare LoRA adapters in weight space (CPU only, no model calls, adapters read only).

For every targeted module (layer x projection) the update is dW = s * B @ A with
s = lora_alpha / r (or lora_alpha / sqrt(r) with use_rslora). Full d_out x d_in
matrices are never built; everything uses r x r products:

  ||dW||_F^2        = s^2 tr((B^T B)(A A^T))
  <dW1, dW2>_F      = s1 s2 tr((B1^T B2)(A2 A1^T))
  column space      = span(B) (QR), row space = span(A^T) (QR)
  Grassmann sim.    = ||Q1^T Q2||_F^2 / r = mean cos^2 of the principal angles
                      (1 = same subspace, random baseline r / d)

Reported per adapter pair: overall cosine (all dW concatenated), median and IQR of
per-module cosines, per projection type and per depth third, cosine of B alone
and of A alone (A starts random and B at zero, so a high A cosine means a shared
initialisation seed), subspace similarity with its random baseline, norm ratios,
and adapter_config differences.

Usage (repository root, WSL):
  .venv_wsl/bin/python scripts/analysis/adapter_weight_similarity.py \\
    --adapter b2_testing=~/experiments/llm-ontology-v3/b2_testing/checkpoints/final_adapter \\
    --adapter b2_testing_onto=... --out-json docs/results/adapter_weight_similarity.json \\
    --out-md docs/results/adapter_weight_similarity.md
"""
import argparse
import hashlib
import itertools
import json
import math
import re
import time
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file

KEY = re.compile(r"layers\.(\d+)\.(\w+)\.(\w+)\.lora_([AB])\.weight$")
CONFIG_FIELDS = ["r", "lora_alpha", "lora_dropout", "use_rslora", "use_dora", "bias",
                 "init_lora_weights", "target_modules", "base_model_name_or_path", "peft_version"]


def load_adapter(path):
    path = Path(path).expanduser()
    cfg = json.loads((path / "adapter_config.json").read_text())
    r = cfg["r"]
    scale = cfg["lora_alpha"] / (math.sqrt(r) if cfg.get("use_rslora") else r)
    tensors = load_file(str(path / "adapter_model.safetensors"))
    mods = {}
    for k, v in tensors.items():
        m = KEY.search(k)
        if not m:
            continue
        layer, block, proj, ab = int(m.group(1)), m.group(2), m.group(3), m.group(4)
        mods.setdefault((layer, f"{block}.{proj}"), {})[ab] = v.astype(np.float64)
    sha = hashlib.sha256((path / "adapter_model.safetensors").read_bytes()).hexdigest()
    return {"path": str(path).replace(str(Path.home()), "~"), "config": cfg, "scale": scale, "modules": mods, "sha256": sha}


def orth(m):
    q, _ = np.linalg.qr(m)
    return q


def module_stats(m1, s1, m2, s2):
    a1, b1, a2, b2 = m1["A"], m1["B"], m2["A"], m2["B"]
    n1 = s1 * s1 * np.trace((b1.T @ b1) @ (a1 @ a1.T))
    n2 = s2 * s2 * np.trace((b2.T @ b2) @ (a2 @ a2.T))
    inner = s1 * s2 * np.trace((b1.T @ b2) @ (a2 @ a1.T))
    qb1, qb2 = orth(b1), orth(b2)
    qa1, qa2 = orth(a1.T), orth(a2.T)
    r = a1.shape[0]
    col = float(np.sum((qb1.T @ qb2) ** 2) / r)
    row = float(np.sum((qa1.T @ qa2) ** 2) / r)
    cos = lambda x, y: float(np.sum(x * y) / math.sqrt(np.sum(x * x) * np.sum(y * y)))  # noqa: E731
    return {"n1": float(n1), "n2": float(n2), "inner": float(inner),
            "cos": float(inner / math.sqrt(n1 * n2)), "cos_A": cos(a1, a2), "cos_B": cos(b1, b2),
            "col_sim": col, "row_sim": row,
            "col_base": r / b1.shape[0], "row_base": r / a1.shape[1]}


def summarise(rows):
    def agg(sel):
        if not sel:
            return None
        inner = sum(x["inner"] for x in sel)
        n1 = sum(x["n1"] for x in sel)
        n2 = sum(x["n2"] for x in sel)
        cs = np.array([x["cos"] for x in sel])
        return {"modules": len(sel), "overall_cos": inner / math.sqrt(n1 * n2),
                "median_cos": float(np.median(cs)), "iqr_cos": [float(np.percentile(cs, 25)), float(np.percentile(cs, 75))],
                "mean_cos_A": float(np.mean([x["cos_A"] for x in sel])),
                "mean_cos_B": float(np.mean([x["cos_B"] for x in sel])),
                "col_sim": float(np.mean([x["col_sim"] for x in sel])), "col_base": float(np.mean([x["col_base"] for x in sel])),
                "row_sim": float(np.mean([x["row_sim"] for x in sel])), "row_base": float(np.mean([x["row_base"] for x in sel])),
                "norm1": math.sqrt(n1), "norm2": math.sqrt(n2), "norm_ratio": math.sqrt(n1 / n2)}
    layers = sorted({x["layer"] for x in rows})
    thirds = np.array_split(np.array(layers), 3)
    out = {"overall": agg(rows),
           "by_module": {p: agg([x for x in rows if x["proj"] == p]) for p in sorted({x["proj"] for x in rows})},
           "by_depth": {f"L{int(t[0])}-{int(t[-1])}": agg([x for x in rows if x["layer"] in set(t.tolist())]) for t in thirds}}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--adapter", action="append", required=True, help="name=path/to/final_adapter")
    ap.add_argument("--pair", action="append", help="nameA:nameB (default: all pairs)")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--notes", help="optional Markdown interpretation appended to --out-md")
    args = ap.parse_args()
    t0 = time.time()
    adapters = {}
    for spec in args.adapter:
        name, path = spec.split("=", 1)
        adapters[name] = load_adapter(path)
    names = list(adapters)
    pairs = [tuple(p.split(":")) for p in args.pair] if args.pair else list(itertools.combinations(names, 2))
    cfg_diff = {}
    for f in CONFIG_FIELDS:
        vals = {n: adapters[n]["config"].get(f) for n in names}
        norm = {n: (sorted(v) if isinstance(v, list) else v) for n, v in vals.items()}
        cfg_diff[f] = {"values": norm, "same": len({json.dumps(v, sort_keys=True) for v in norm.values()}) == 1}
    per_adapter = {}
    for n in names:
        a = adapters[n]
        norms = [a["scale"] ** 2 * float(np.trace((m["B"].T @ m["B"]) @ (m["A"] @ m["A"].T))) for m in a["modules"].values()]
        per_adapter[n] = {"sha256": a["sha256"], "scale": a["scale"], "modules": len(a["modules"]),
                          "total_norm": math.sqrt(sum(norms)), "median_module_norm": float(np.median(np.sqrt(norms)))}
    results = {}
    for x, y in pairs:
        ax, ay = adapters[x], adapters[y]
        keys = sorted(set(ax["modules"]) & set(ay["modules"]))
        rows = []
        for k in keys:
            s = module_stats(ax["modules"][k], ax["scale"], ay["modules"][k], ay["scale"])
            rows.append({"layer": k[0], "proj": k[1].split(".")[-1], **s})
        results[f"{x} vs {y}"] = {"a": x, "b": y, "missing_modules": len(set(ax["modules"]) ^ set(ay["modules"])),
                                  **summarise(rows), "per_module": rows}
    out = {"adapters": per_adapter, "config_differences": cfg_diff, "pairs": results,
           "runtime_seconds": round(time.time() - t0, 1)}
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(out, indent=1))
    write_md(out, Path(args.out_md), Path(args.notes) if args.notes else None)
    print("OK", args.out_json, args.out_md, out["runtime_seconds"], "s")


def f3(x):
    return f"{x:.3f}"


def write_md(out, path, notes=None):
    L = ["# Adaptéry vo váhovom priestore", "",
         "Porovnanie štyroch LoRA adaptérov v3 priamo vo váhach, bez modelu a bez GPU "
         "(`scripts/analysis/adapter_weight_similarity.py`). Pre každý cieľový modul je aktualizácia "
         "ΔW = s·B·A (s = lora_alpha / r); plné matice sa nevytvárajú, všetko sa počíta cez r×r súčiny.", "",
         "## Adaptéry", "", "| Adaptér | modulov | škála s | ‖ΔW‖_F spolu | medián ‖ΔW‖_F modulu | sha256 |",
         "|---|---:|---:|---:|---:|---|"]
    for n, a in out["adapters"].items():
        L.append(f"| {n} | {a['modules']} | {a['scale']:g} | {f3(a['total_norm'])} | {f3(a['median_module_norm'])} | `{a['sha256'][:12]}…` |")
    L += ["", "## Konfigurácia", "", "| pole | rovnaké | hodnoty |", "|---|---|---|"]
    for f, d in out["config_differences"].items():
        vals = d["values"]
        shown = json.dumps(next(iter(vals.values())), ensure_ascii=False) if d["same"] else "; ".join(f"{k}: {json.dumps(v)}" for k, v in vals.items())
        L.append(f"| `{f}` | {'áno' if d['same'] else '**nie**'} | {shown} |")
    L += ["", "## Páry: celkové čísla", "",
          "*cos ΔW* = kosínus všetkých ΔW spojených do jedného vektora; *medián / IQR* cez moduly; "
          "*cos A*, *cos B* = priemerný kosínus samotných matíc; *stĺpce* = Grassmannova podobnosť "
          "priestorov span(B) (výstupná strana), *riadky* = span(Aᵀ) (vstupná strana), v zátvorke náhodný baseline r/d; "
          "*pomer noriem* = ‖ΔW_A‖ / ‖ΔW_B‖.", "",
          "| Pár | cos ΔW | medián cos (IQR) | cos A | cos B | stĺpce (baseline) | riadky (baseline) | pomer noriem |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k, p in out["pairs"].items():
        o = p["overall"]
        L.append(f"| {k} | {f3(o['overall_cos'])} | {f3(o['median_cos'])} ({f3(o['iqr_cos'][0])}–{f3(o['iqr_cos'][1])}) | "
                 f"{f3(o['mean_cos_A'])} | {f3(o['mean_cos_B'])} | {f3(o['col_sim'])} ({o['col_base']:.4f}) | "
                 f"{f3(o['row_sim'])} ({o['row_base']:.4f}) | {f3(o['norm_ratio'])} |")
    for title, key in [("Podľa typu projekcie", "by_module"), ("Podľa hĺbky (tretiny vrstiev)", "by_depth")]:
        groups = list(next(iter(out["pairs"].values()))[key])
        L += ["", f"## {title}: cos ΔW (stĺpcová podobnosť)", "", "| Pár | " + " | ".join(groups) + " |",
              "|---|" + "---:|" * len(groups)]
        for k, p in out["pairs"].items():
            L.append(f"| {k} | " + " | ".join(f"{f3(p[key][g]['overall_cos'])} ({f3(p[key][g]['col_sim'])})" for g in groups) + " |")
    L += ["", f"Výpočet trval {out['runtime_seconds']} s na CPU.", ""]
    if notes and notes.exists():
        L += [notes.read_text().rstrip(), ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))


if __name__ == "__main__":
    main()
