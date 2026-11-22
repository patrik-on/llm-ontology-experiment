"""Deep analysis of two finished eval matrices, computed only from stored run files.

No model calls and no GPU; the run directories are read only. Computes:

Testing (Methods2Test matrix)
  T1 failure taxonomy per arm (not assembled / javac error classes / runtime / pass)
     and method line credit; T2 discordant cases of the primary pairs and
     rag_single vs qwen_base with flip categories; T3 subgroups of the focal method
     (branches, throws, LOC tertiles, other project types, class LOC); T4 ontology
     block length, boundary candidates and symbols invented from the block; T5 RAG
     contexts, scores, same project/class, leakage and symbols copied from
     retrieval; T6 prompt length versus pass.
Refactoring (SWE + MaRV + ML4Ref matrix)
  R1 status per arm x source x operation; R2 which checks failed and what
     RefactoringMiner detected instead; R3 discordant cases; R4 rag_single no_op
     and retrieval diagnostics; R5 fine-tuned arms on the SWE subset.
Both
  Wilson 95 % intervals, paired bootstrap (10 000, seed 42) intervals for the
  primary pairs, McNemar minimum detectable effect at 80 % power, and
  descriptive cross-backend comparisons.

Writes results.md, results.json and examples.md to --out. An optional
hand-written findings section (--summary) is inserted before the TESTING section.

Usage (from the repository root, WSL):
  .venv_wsl/bin/python scripts/analysis/deep_analysis.py
"""
import argparse
import ast
import collections
import difflib
import json
import math
import re
import statistics as st
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binom, binomtest, mannwhitneyu

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from llm_ontology.core.paths import env_root, project_root, resolve_path

_ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
_ap.add_argument("--testing-run", default="artifacts/evaluation/runs/testing-matrix-20261122-rag2")
_ap.add_argument("--refactoring-run", default="artifacts/evaluation/runs/refactoring-matrix-20261121")
_ap.add_argument("--out", default="artifacts/analysis/deep-20261122")
_ap.add_argument("--summary", default="scripts/analysis/deep_analysis_summary_20261122.md",
                 help="Markdown findings inserted into results.md; pass '' to skip")
_ap.add_argument("--tokenizer", default=str(Path(env_root("LLM_ONTOLOGY_MODELS_ROOT"),
                                                 "huggingface/Qwen2.5-Coder-7B-Instruct")))
ARGS = _ap.parse_args()

REPO = project_root()
TR = resolve_path(ARGS.testing_run)
RR = resolve_path(ARGS.refactoring_run)
OUT = resolve_path(ARGS.out)
OUT.mkdir(parents=True, exist_ok=True)
TOK_PATH = ARGS.tokenizer

T_ARMS = ['qwen_base', 'onto_project', 'skills', 'skills_onto', 'rag_single', 'ft_testing', 'ft_v3_onto', 'ft_onto']
R_ARMS = ['qwen_base', 'onto_project', 'skills', 'skills_onto', 'rag_single', 'ft_refactoring', 'ft_v3_onto', 'ft_onto']
T_PAIRS = [('onto_project', 'qwen_base'), ('ft_v3_onto', 'ft_testing'), ('ft_onto', 'ft_v3_onto'),
           ('skills_onto', 'skills'), ('skills_onto', 'onto_project')]
R_PAIRS = [('onto_project', 'qwen_base'), ('ft_v3_onto', 'ft_refactoring'), ('ft_onto', 'ft_v3_onto'),
           ('skills_onto', 'skills'), ('skills_onto', 'onto_project')]
EXTRA = [('rag_single', 'qwen_base')]
ONTO_PARTNER = {'onto_project': 'qwen_base', 'skills_onto': 'skills', 'ft_v3_onto': None, 'ft_onto': None}

R = {}        # results.json
MD = []       # results.md lines
EX = []       # examples.md lines


def rj(p):
    return json.loads(Path(p).read_text())


def md(*lines):
    MD.extend(lines)


def table(header, rows):
    out = ["| " + " | ".join(map(str, header)) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(map(str, r)) + " |" for r in rows]
    md(*out, "")


def wilson(k, n, z=1.959964):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def pct(x):
    return f"{100 * x:.1f}"


def mcnemar(a, b):
    """a,b: lists of bool (paired). Return (A only, B only, exact p)."""
    ao = sum(x and not y for x, y in zip(a, b))
    bo = sum(y and not x for x, y in zip(a, b))
    p = binomtest(ao, ao + bo).pvalue if ao + bo else 1.0
    return ao, bo, float(p)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj = [0] * len(ps)
    run = 0
    for rank, i in enumerate(order):
        run = max(run, min(1, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def boot_ci(a, b, n=10000, seed=42):
    rng = np.random.default_rng(seed)
    d = np.array(a, float) - np.array(b, float)
    idx = rng.integers(0, len(d), size=(n, len(d)))
    m = d[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def mcnemar_power(n, pd, delta, alpha):
    """Exact conditional McNemar power: D~Bin(n,pd); b|D~Bin(D,(pd+delta)/(2pd))."""
    if pd <= 0 or abs(delta) > pd:
        return float('nan')
    p1 = (pd + delta) / (2 * pd)
    pw = 0.0
    for D in range(1, n + 1):
        wD = binom.pmf(D, n, pd)
        if wD < 1e-12:
            continue
        # rejection region for two-sided exact binomial test at p=0.5
        ks = np.arange(D + 1)
        pv = np.array([min(1, 2 * min(binom.cdf(k, D, .5), binom.sf(k - 1, D, .5))) for k in ks])
        rej = ks[pv <= alpha]
        pw += wD * binom.pmf(rej, D, p1).sum()
    return pw


def mde(n, pd, alpha, power=0.8):
    for d100 in range(1, 101):
        d = d100 / 100
        if d > pd:
            return None
        if mcnemar_power(n, pd, d, alpha) >= power:
            return d
    return None


def stats_block(name, arms, pairs, succ, ids, extra_desc):
    """succ[arm][id] -> bool"""
    out = {"wilson": {}, "pairs": [], "descriptive": []}
    rows = []
    for a in arms:
        k = sum(succ[a][i] for i in ids)
        lo, hi = wilson(k, len(ids))
        out["wilson"][a] = {"k": k, "n": len(ids), "lower": lo, "upper": hi}
        rows.append([a, f"{k}/{len(ids)}", f"{pct(lo)}–{pct(hi)} %"])
    md(f"### {name}: Wilson 95 % CI na rameno", "")
    table(["Rameno", "Úspech", "Wilson 95 %"], rows)
    res = []
    for A, B in pairs:
        va = [succ[A][i] for i in ids]
        vb = [succ[B][i] for i in ids]
        ao, bo, p = mcnemar(va, vb)
        lo, hi = boot_ci(va, vb)
        pd = (ao + bo) / len(ids)
        res.append(dict(A=A, B=B, a_only=ao, b_only=bo, delta=(sum(va) - sum(vb)) / len(ids), p=p,
                        boot_lo=lo, boot_hi=hi, discordant_rate=pd,
                        mde_005=mde(len(ids), pd, 0.05), mde_holm_001=mde(len(ids), pd, 0.01)))
    for r, h in zip(res, holm([r['p'] for r in res])):
        r['p_holm'] = h
    out["pairs"] = res
    md(f"### {name}: primárne páry – paired bootstrap (10 000, seed 42) a MDE (80 % sila, exaktný McNemar)", "",
       "MDE = najmenší skutočný rozdiel v p.b., ktorý by test pri pozorovanej miere nesúhlasných párov a n=100 odhalil s 80 % silou; "
       "α=0,05 nekorigované, α=0,01 ≈ Holm pre najmenšie p z 5 párov.", "")
    table(["A vs B", "A only / B only", "Δ (p.b.)", "bootstrap 95 % CI", "p", "p Holm", "nesúhlasné", "MDE α=0,05", "MDE α=0,01"],
          [[f"{r['A']} vs {r['B']}", f"{r['a_only']}/{r['b_only']}", f"{100*r['delta']:+.1f}",
            f"{100*r['boot_lo']:+.1f} až {100*r['boot_hi']:+.1f}", f"{r['p']:.4f}", f"{r['p_holm']:.4f}",
            f"{100*r['discordant_rate']:.0f} %",
            ("±" + str(round(100 * r['mde_005']))) if r['mde_005'] else "nedosiahnuteľné",
            ("±" + str(round(100 * r['mde_holm_001']))) if r['mde_holm_001'] else "nedosiahnuteľné"] for r in res])
    drows = []
    for A, B in extra_desc:
        va = [succ[A][i] for i in ids]
        vb = [succ[B][i] for i in ids]
        ao, bo, p = mcnemar(va, vb)
        lo, hi = boot_ci(va, vb)
        out["descriptive"].append(dict(A=A, B=B, a_only=ao, b_only=bo, delta=(sum(va) - sum(vb)) / len(ids), p=p, boot_lo=lo, boot_hi=hi))
        drows.append([f"{A} vs {B}", f"{ao}/{bo}", f"{100*(sum(va)-sum(vb))/len(ids):+.1f}", f"{100*lo:+.1f} až {100*hi:+.1f}", f"{p:.2g}"])
    md(f"### {name}: doplnkové porovnania (DESKRIPTÍVNE – iný backend alebo mimo predeklarovaných párov, bez Holma)", "")
    table(["A vs B", "A only / B only", "Δ (p.b.)", "bootstrap 95 % CI", "p (nekorigované)"], drows)
    return out


# ---------------------------------------------------------------- tokenizer
try:
    from transformers import AutoTokenizer
    TOK = AutoTokenizer.from_pretrained(TOK_PATH)
    def ntok(s):
        return len(TOK.encode(s, add_special_tokens=False))
    TOK_NOTE = "Qwen2.5-Coder-7B-Instruct tokenizer (CPU)"
except Exception as e:  # pragma: no cover
    def ntok(s):
        return math.ceil(len(s) / 3.5)
    TOK_NOTE = f"tokenizer unavailable ({e}); chars/3.5 estimate"

# ================================================================ TESTING
agg = rj(TR / "reports/aggregate.json")
ids = agg["cases"]
cell = {(m["arm"], m["id"]): m for m in agg["paired_matrix"]}
case_dir = {i: TR / "cases" / i for i in ids}
case_json = {i: rj(case_dir[i] / "case.json") for i in ids}
prepared = {i: rj(case_dir[i] / "prepared.json") for i in ids}
block = {i: (case_dir[i] / "ontology/block.txt").read_text() for i in ids}
src = {i: case_json[i]["input_text"] for i in ids}

md("# Hĺbková analýza evalu (2026-11-22)", "",
   "Zdroj: len uložené výsledky (`testing-matrix-20261122-rag2`, `refactoring-matrix-20261121`), žiadne volania modelu ani GPU. "
   f"Tokeny: {TOK_NOTE}. Prípady sú zvolené zo zdrojov s fixnými kvótami (convenience), často zoskupené podľa projektu – "
   "všetky p-hodnoty sú podmienené týmito prípadmi.", "")

# ---- T1 failure taxonomy
SYM_RE = re.compile(r"symbol:\s+(variable|method|class|constructor|static)\s+([A-Za-z_$][\w$]*)")


def compile_errors(log):
    errs = []
    lines = log.splitlines()
    for k, ln in enumerate(lines):
        m = re.search(r"error: (.*)$", ln)
        if not m:
            continue
        msg = m.group(1)
        sym = None
        for nxt in lines[k + 1:k + 6]:
            s = SYM_RE.search(nxt)
            if s:
                sym = (s.group(1), s.group(2))
                break
            if "error:" in nxt:
                break
        errs.append((msg, sym))
    return errs


def classify_compile(msg, sym):
    if msg.startswith("cannot find symbol"):
        return "cannot_find_symbol:" + (sym[0] if sym else "?")
    if msg.startswith("incompatible types"):
        return "incompatible_types"
    if msg.startswith("unreported exception"):
        return "unreported_exception"
    if "private access" in msg or "has protected access" in msg or "not public" in msg:
        return "access_violation"
    if "cannot be applied to given types" in msg or "no suitable method" in msg or "no suitable constructor" in msg:
        return "wrong_arguments"
    if re.match(r"(unclosed string literal|illegal escape character|not a statement|'.+' expected|illegal start of|integer number too large|unclosed character literal|'void' type not allowed)", msg):
        return "syntax"
    return "other_compile"


tcells = {}
for a in T_ARMS:
    for i in ids:
        m = cell[(a, i)]
        pdir = case_dir[i] / "predictions" / a
        info = {"pass": bool(m.get("class_pass")), "input_tokens": m.get("input_tokens") or 0,
                "output_tokens": m.get("output_tokens") or 0}
        cov = 0.0
        try:
            cov = m["coverage"]["method"]["counters"]["line"]["ratio"] if m.get("class_pass") else 0.0
        except Exception:
            cov = 0.0
        info["method_line_credit"] = cov
        info["compile_errors"] = []
        if not m.get("assembled"):
            err = (m.get("failure") or {}).get("error") if isinstance(m.get("failure"), dict) else str(m.get("failure"))
            e = (err or "").lower()
            if "not balanced" in e:
                sub = "unbalanced_body"
            elif "empty body" in e or "unicode escape" in e:
                sub = "empty_or_escape"
            elif "prohibited declaration" in e:
                sub = "forbidden_construct"
            elif any(k in e for k in ["unterminated string", "expecting", "invalid \\escape", "validation error", "structured output"]):
                sub = "invalid_json"
            else:
                sub = "other_generation"
            info["cat"] = "not_assembled:" + sub
            info["failure_error"] = err
        elif not m.get("compiled"):
            log = pdir / "coverage-0/evaluation/compile.log"
            errs = compile_errors(log.read_text(errors="replace")) if log.exists() else []
            info["compile_errors"] = errs
            info["cat"] = "compile:" + (classify_compile(*errs[0]) if errs else "no_log")
        else:
            outs = m.get("per_test_outcomes_first_run") or []
            stats = set(m.get("statuses") or [])
            if m.get("class_pass"):
                info["cat"] = "pass"
            elif any(o.get("type") and "AssertionFailedError" not in o["type"] and o.get("status") != "passed" for o in outs):
                info["cat"] = "runtime:unexpected_exception"
            elif "execution_error" in stats:
                info["cat"] = "runtime:execution_error"
            elif "assertion_failure" in stats:
                info["cat"] = "runtime:assertion_failure"
            else:
                info["cat"] = "runtime:other(" + ",".join(sorted(stats)) + ")"
        tcells[(a, i)] = info

cats = sorted({c["cat"] for c in tcells.values()}, key=lambda s: (s.split(":")[0] != "pass", s))
md("## TESTING", "", "### T1. Taxonómia zlyhaní na rameno (prvá chyba kompilácie určuje kategóriu)", "")
rows = []
R["T1"] = {}
for a in T_ARMS:
    c = collections.Counter(tcells[(a, i)]["cat"] for i in ids)
    R["T1"][a] = dict(c)
    rows.append([a] + [c.get(k, 0) for k in cats] + [f"{st.mean(tcells[(a, i)]['method_line_credit'] for i in ids):.3f}"])
table(["Rameno"] + [k.replace("cannot_find_symbol", "CFS").replace("not_assembled", "NA") for k in cats] + ["method line credit"], rows)
md("Timeout: v uložených výsledkoch sa nevyskytol ani jeden (statusy sú len passed / assertion_failure / execution_error / compile_failure). "
   "`runtime:unexpected_exception` = test spadol na inej výnimke než AssertionFailedError (napr. UnsupportedOperationException, NPE). "
   "Method line credit = pokrytie riadkov focal metódy, ak trieda prešla, inak 0.", "")

# all compile errors (not just first)
rows = []
R["T1_all_compile_errors"] = {}
allk = set()
per = {}
for a in T_ARMS:
    c = collections.Counter(classify_compile(*e) for i in ids for e in tcells[(a, i)]["compile_errors"])
    per[a] = c
    allk |= set(c)
allk = sorted(allk)
for a in T_ARMS:
    R["T1_all_compile_errors"][a] = dict(per[a])
    rows.append([a, sum(1 for i in ids if tcells[(a, i)]["cat"].startswith("compile"))] + [per[a].get(k, 0) for k in allk])
md("Všetky javac chyby (nie len prvá) v bunkách, ktoré nekompilovali:", "")
table(["Rameno", "buniek s compile fail"] + [k.replace("cannot_find_symbol", "CFS") for k in allk], rows)

# top missing symbols
md("Najčastejšie chýbajúce symboly (cannot find symbol, unikátne na bunku):", "")
rows = []
for a in T_ARMS:
    c = collections.Counter()
    for i in ids:
        c.update(sorted({e[1][1] for e in tcells[(a, i)]["compile_errors"] if e[1]}))
    rows.append([a, ", ".join(f"{s}×{n}" for s, n in c.most_common(6))])
table(["Rameno", "symboly"], rows)

# ---- T2 discordant flips
md("### T2. Nesúhlasné prípady a ako sa preklopili (kategória B → kategória A)", "")
R["T2"] = {}
for A, B in T_PAIRS + EXTRA:
    gain = [(i, tcells[(B, i)]["cat"]) for i in ids if tcells[(A, i)]["pass"] and not tcells[(B, i)]["pass"]]
    loss = [(i, tcells[(A, i)]["cat"]) for i in ids if tcells[(B, i)]["pass"] and not tcells[(A, i)]["pass"]]
    R["T2"][f"{A} vs {B}"] = {"A_only": gain, "B_only": loss}
    gc = collections.Counter(c for _, c in gain)
    lc = collections.Counter(c for _, c in loss)
    md(f"**{A} vs {B}** – A prešlo, B nie ({len(gain)}): B zlyhalo ako " +
       (", ".join(f"{k} {v}×" for k, v in gc.most_common()) or "–") + ". ",
       f"B prešlo, A nie ({len(loss)}): A zlyhalo ako " + (", ".join(f"{k} {v}×" for k, v in lc.most_common()) or "–") + ".",
       "Prípady A-only: " + (", ".join(i for i, _ in gain) or "–") + "; B-only: " + (", ".join(i for i, _ in loss) or "–"), "")

# ---- T3 subgroups
JDK = set("""String Object Integer Long Double Float Boolean Character Byte Short Math System List ArrayList Map HashMap Set HashSet
Collection Collections Arrays Iterator Iterable Optional Stream Collectors Exception RuntimeException IllegalArgumentException
IllegalStateException NullPointerException IOException StringBuilder StringBuffer Class Enum Number Comparable Comparator
LinkedList TreeMap TreeSet LinkedHashMap LinkedHashSet Objects CharSequence Thread Runnable Void Override Deprecated
UnsupportedOperationException IndexOutOfBoundsException ArrayIndexOutOfBoundsException Date Calendar File Path Paths Files
BigDecimal BigInteger Pattern Matcher UUID Locale TimeUnit Function Supplier Consumer Predicate BiFunction Queue Deque
ArrayDeque Vector Hashtable Properties Random InputStream OutputStream Reader Writer URL URI Charset StandardCharsets
NumberFormatException ClassCastException CloneNotSupportedException InterruptedException Throwable Error SuppressWarnings
SafeVarargs FunctionalInterface AutoCloseable Closeable Entry ConcurrentHashMap AtomicInteger AtomicLong Instant Duration
LocalDate LocalDateTime ZonedDateTime Base64 SimpleDateFormat DateFormat Iterable NoSuchElementException SecurityException""".split())


def focal_method_text(i):
    s = src[i]
    name = prepared[i]["focal_method_name"]
    for m in re.finditer(r"[^\n;{}]*\b" + re.escape(name) + r"\s*\([^)]*\)[^{;]*\{", s):
        start = m.start()
        depth, k = 0, m.end() - 1
        while k < len(s):
            if s[k] == "{":
                depth += 1
            elif s[k] == "}":
                depth -= 1
                if depth == 0:
                    return s[start:k + 1]
            k += 1
    return None


def strip_strings(t):
    t = re.sub(r'"(\\.|[^"\\])*"', '""', t)
    t = re.sub(r"'(\\.|[^'\\])*'", "''", t)
    t = re.sub(r"//[^\n]*", "", t)
    return re.sub(r"/\*.*?\*/", "", t, flags=re.S)


feat = {}
nofm = []
for i in ids:
    fm = focal_method_text(i)
    if fm is None:
        nofm.append(i)
        fm = ""
    t = strip_strings(fm)
    br = len(re.findall(r"\b(if|for|while|case|catch)\b", t)) + t.count("?") - t.count("?>") - len(re.findall(r"<\s*\?", t)) + len(re.findall(r"\bdo\s*\{", t))
    br = max(br, 0)
    loc = sum(1 for line in fm.splitlines() if line.strip())
    sig = fm.split("{", 1)[0]
    fcls = prepared[i]["focal_class"].split(".")[-1]
    types = {x for x in re.findall(r"\b([A-Z][A-Za-z0-9_]*[a-z][A-Za-z0-9_]*)\b", t)} - JDK - {fcls}
    feat[i] = {"branches": br, "throws": bool(re.search(r"\bthrows\b", sig) or re.search(r"\bthrow\b", t)),
               "method_loc": loc, "other_types": len(types), "class_loc": sum(1 for line in src[i].splitlines() if line.strip())}

loc_t = np.percentile([feat[i]["method_loc"] for i in ids], [33.333, 66.667])
cls_t = np.percentile([feat[i]["class_loc"] for i in ids], [33.333, 66.667])


def tert(v, t):
    return "T1 (nízke)" if v <= t[0] else ("T2" if v <= t[1] else "T3 (vysoké)")


groups = {
    "vetvenie": lambda i: "0" if feat[i]["branches"] == 0 else ("1–2" if feat[i]["branches"] <= 2 else "3+"),
    "throws/throw": lambda i: "áno" if feat[i]["throws"] else "nie",
    f"LOC metódy (tercily ≤{loc_t[0]:.0f}, ≤{loc_t[1]:.0f})": lambda i: tert(feat[i]["method_loc"], loc_t),
    "iné projektové typy v metóde": lambda i: "0" if feat[i]["other_types"] == 0 else ("1–2" if feat[i]["other_types"] <= 2 else "3+"),
    f"LOC triedy (tercily ≤{cls_t[0]:.0f}, ≤{cls_t[1]:.0f})": lambda i: tert(feat[i]["class_loc"], cls_t),
}
md("### T3. Podskupiny podľa focal metódy (pass rate na rameno; Δ = rozdiel v p.b. s počtom A-only/B-only)", "",
   "Heuristiky zo zdroja v `case.json` (`input_text`): vetvenie = if/for/while/case/catch/do/ternárny `?`; "
   "iné projektové typy = identifikátory s veľkým začiatočným písmenom v tele metódy mimo bežných JDK typov a mimo samotnej triedy (aproximácia). "
   + (f"Focal metódu sa nepodarilo vystrihnúť v {len(nofm)} prípadoch ({', '.join(nofm)}) – tie majú nulové príznaky." if nofm else ""), "")
R["T3"] = {}
for gname, fn in groups.items():
    levels = sorted({fn(i) for i in ids})
    rows = []
    R["T3"][gname] = {}
    for lv in levels:
        sub = [i for i in ids if fn(i) == lv]
        r = [lv, len(sub)] + [f"{sum(tcells[(a, i)]['pass'] for i in sub)}" for a in T_ARMS]
        for A, B in [('onto_project', 'qwen_base'), ('rag_single', 'qwen_base')]:
            ao = sum(tcells[(A, i)]['pass'] and not tcells[(B, i)]['pass'] for i in sub)
            bo = sum(tcells[(B, i)]['pass'] and not tcells[(A, i)]['pass'] for i in sub)
            r.append(f"{100*(ao-bo)/len(sub):+.0f} ({ao}/{bo})")
        rows.append(r)
        R["T3"][gname][lv] = {"n": len(sub), **{a: sum(tcells[(a, i)]['pass'] for i in sub) for a in T_ARMS}}
    md(f"**{gname}**", "")
    table(["úroveň", "n"] + T_ARMS + ["Δ onto−base", "Δ rag−base"], rows)

# ---- T4 ontology
md("### T4. Ontológia", "")
btok = {i: ntok(block[i]) for i in ids}
hasb = {i: "Boundary candidates:" in block[i] for i in ids}
bt = np.percentile(list(btok.values()), [33.333, 66.667])
rows = []
for lv in ["T1 (nízke)", "T2", "T3 (vysoké)"]:
    sub = [i for i in ids if tert(btok[i], bt) == lv]
    rows.append([lv, len(sub), f"{min(btok[i] for i in sub)}–{max(btok[i] for i in sub)}"] +
                [sum(tcells[(a, i)]['pass'] for i in sub) for a in ['qwen_base', 'onto_project', 'skills', 'skills_onto', 'ft_v3_onto', 'ft_onto']])
md(f"Dĺžka bloku v tokenoch: medián {st.median(btok.values()):.0f}, rozsah {min(btok.values())}–{max(btok.values())}. Pass podľa tercilu dĺžky bloku:", "")
table(["tercil", "n", "tokeny", "qwen_base", "onto_project", "skills", "skills_onto", "ft_v3_onto", "ft_onto"], rows)
rows = []
for lv in [True, False]:
    sub = [i for i in ids if hasb[i] == lv]
    rows.append(["áno" if lv else "nie", len(sub)] + [sum(tcells[(a, i)]['pass'] for i in sub) for a in ['qwen_base', 'onto_project', 'skills', 'skills_onto', 'ft_v3_onto', 'ft_onto']])
md("Prítomnosť riadku „Boundary candidates“ v bloku:", "")
table(["boundary", "n", "qwen_base", "onto_project", "skills", "skills_onto", "ft_v3_onto", "ft_onto"], rows)


def word_in(w, text):
    return re.search(r"(?<![\w$])" + re.escape(w) + r"(?![\w$])", text) is not None


inv = {}
inv_ex = []
for a in T_ARMS:
    n_cells = n_sym = 0
    for i in ids:
        syms = {e[1][1] for e in tcells[(a, i)]["compile_errors"] if e[1] and e[0].startswith("cannot find symbol")}
        hit = [s for s in sorted(syms) if word_in(s, block[i]) and not word_in(s, src[i])]
        if hit:
            n_cells += 1
            n_sym += len(hit)
            if a in ONTO_PARTNER:
                inv_ex.append((a, i, hit))
    inv[a] = {"cells": n_cells, "symbols": n_sym}
R["T4"] = {"block_tokens": btok, "boundary": hasb, "invented_from_block": inv}
md("„Cannot find symbol“, ktorého symbol je v ontologickom bloku, ale NIE v zdrojovom kóde (vymyslené z bloku). "
   "Pre ne-onto ramená je to kontrolný výskyt (rovnaký blok prípadu, ktorý model nevidel):", "")
table(["Rameno", "vidí blok", "buniek", "symbolov"], [[a, "áno" if a in ONTO_PARTNER else "nie", inv[a]["cells"], inv[a]["symbols"]] for a in T_ARMS])

# ---- T5 RAG
md("### T5. RAG (rag_single, testing)", "")
rag = {}
for i in ids:
    # frozen retrieval (the continuation replays the frozen request; preview_trace holds its retrieval)
    tr = rj(case_dir[i] / "frozen_prompts/rag_single/preview_trace.json")["failure_metadata"]["retrieval_trace"]
    docs = tr["retrieved_documents"]
    pids = tr.get("prompt_document_ids")
    if pids:
        docs = [x for x in docs if x["document_id"] in pids]
    tb = {"retrieval_tokens": tr.get("estimated_context_tokens")}
    proj = prepared[i]["project_id"]
    fcls = prepared[i]["focal_class"].split(".")[-1]
    fmn = prepared[i]["focal_method_name"]
    info = {"n_docs": len(docs), "scores": [x.get("score") for x in docs], "rerank": [x.get("reranking_score") for x in docs],
            "same_project": 0, "same_class": 0, "same_class_and_method_test": 0,
            "retrieval_tokens": tb.get("retrieval_tokens"), "final_prompt_tokens": tb.get("final_prompt_tokens"), "content": ""}
    for x in docs:
        meta = x.get("metadata") or {}
        sf = str(meta.get("source_file", ""))
        dproj = sf.split("/")[-2] if "/" in sf else ""
        content = x.get("content", "")
        info["content"] += "\n" + content
        if dproj == proj:
            info["same_project"] += 1
        test_part = content.split("Corresponding test code:", 1)[-1] if "Corresponding test code:" in content else ""
        prod_part = content.split("Corresponding test code:", 1)[0]
        if word_in(fcls, prod_part) or meta.get("class_name") == fcls:
            info["same_class"] += 1
        if word_in(fcls, test_part) and word_in(fmn, test_part):
            info["same_class_and_method_test"] += 1
    rag[i] = info
nd = collections.Counter(r["n_docs"] for r in rag.values())
sc = [s for r in rag.values() for s in r["scores"] if s is not None]
pq = [tcells[('qwen_base', i)]["input_tokens"] for i in ids]
pr = [tcells[('rag_single', i)]["input_tokens"] for i in ids]
sp = sum(1 for r in rag.values() if r["same_project"])
scl = sum(1 for r in rag.values() if r["same_class"])
leak = [i for i, r in rag.items() if r["same_class_and_method_test"]]
copied = {}
copied_ex = []
for a in ['rag_single', 'qwen_base']:
    n_cells = n_sym = 0
    for i in ids:
        syms = {e[1][1] for e in tcells[(a, i)]["compile_errors"] if e[1] and e[0].startswith("cannot find symbol")}
        hit = [s for s in sorted(syms) if word_in(s, rag[i]["content"]) and not word_in(s, src[i])]
        proj_hit = [s for s in hit if s not in JDK]
        if hit:
            n_cells += 1
            n_sym += len(hit)
        if proj_hit:
            n_pc = copied.setdefault(a + "_project_cells", [])
            n_pc.append((i, proj_hit))
            if a == 'rag_single':
                copied_ex.append((i, proj_hit))
    copied[a] = {"cells": n_cells, "symbols": n_sym, "project_symbol_cells": len(copied.get(a + "_project_cells", []))}
R["T5"] = {"n_docs": dict(nd), "score_median": st.median(sc), "score_min": min(sc), "score_max": max(sc),
           "same_project_cases": sp, "same_class_cases": scl, "leak_cases": leak,
           "prompt_tokens_median": {"qwen_base": st.median(pq), "rag_single": st.median(pr)}, "copied_from_retrieval": copied}
rows = [["počet kontextov na prípad", ", ".join(f"{k}: {v}×" for k, v in sorted(nd.items()))],
        ["similarity score (bge-m3) medián / min / max", f"{st.median(sc):.3f} / {min(sc):.3f} / {max(sc):.3f}"],
        ["prípady s ≥1 kontextom z rovnakého projektu", f"{sp}/100"],
        ["prípady s ≥1 kontextom o rovnakej triede (meno triedy v produkčnom kóde)", f"{scl}/100"],
        ["LEAKAGE: retrieved test volá rovnakú triedu aj focal metódu", f"{len(leak)}/100" + (f" ({', '.join(leak)})" if leak else "")],
        ["prompt tokeny medián qwen_base → rag_single", f"{st.median(pq):.0f} → {st.median(pr):.0f} (+{st.median(pr)-st.median(pq):.0f})"],
        ["retrieval tokeny medián", f"{st.median([r['retrieval_tokens'] for r in rag.values() if r['retrieval_tokens']]):.0f}"],
        ["CFS symbol je v retrieved kontexte, nie v zdroji – rag_single (všetky / len projektové, nie JDK)", f"{copied['rag_single']['cells']} buniek / {copied['rag_single']['symbols']} symbolov; projektové: {copied['rag_single']['project_symbol_cells']} buniek ({'; '.join(i + ': ' + ','.join(h) for i, h in copied.get('rag_single_project_cells', []))})"],
        ["to isté pre qwen_base (kontrola, kontext nevidel)", f"{copied['qwen_base']['cells']} buniek / {copied['qwen_base']['symbols']} symbolov; projektové: {copied['qwen_base']['project_symbol_cells']}"]]
table(["Metrika", "Hodnota"], rows)
# pass by same project
rows = []
for lv in [True, False]:
    sub = [i for i in ids if bool(rag[i]["same_project"]) == lv]
    rows.append(["áno" if lv else "nie", len(sub), sum(tcells[('qwen_base', i)]['pass'] for i in sub), sum(tcells[('rag_single', i)]['pass'] for i in sub)])
md("Pass podľa toho, či retrieval priniesol kontext z rovnakého projektu:", "")
table(["rovnaký projekt", "n", "qwen_base", "rag_single"], rows)

# ---- T6 prompt length vs pass
md("### T6. Dĺžka promptu (input tokeny) vs. pass", "")
rows = []
R["T6"] = {}
for a in T_ARMS:
    toks = [tcells[(a, i)]["input_tokens"] for i in ids]
    t3 = np.percentile(toks, [33.333, 66.667])
    def lv(v):
        return 0 if v <= t3[0] else (1 if v <= t3[1] else 2)
    cnt = [[0, 0] for _ in range(3)]
    for i in ids:
        c = cnt[lv(tcells[(a, i)]["input_tokens"])]
        c[0] += tcells[(a, i)]["pass"]
        c[1] += 1
    pt = [tcells[(a, i)]["input_tokens"] for i in ids if tcells[(a, i)]["pass"]]
    ft_ = [tcells[(a, i)]["input_tokens"] for i in ids if not tcells[(a, i)]["pass"]]
    p = mannwhitneyu(pt, ft_).pvalue if pt and ft_ else float('nan')
    R["T6"][a] = {"tertiles": cnt, "median_pass": st.median(pt) if pt else None, "median_fail": st.median(ft_), "mwu_p": p}
    rows.append([a, f"{st.median(toks):.0f}", *[f"{c[0]}/{c[1]}" for c in cnt], f"{st.median(pt):.0f}" if pt else "–", f"{st.median(ft_):.0f}", f"{p:.3f}"])
table(["Rameno", "medián tokenov", "pass T1", "pass T2", "pass T3", "medián pass", "medián fail", "Mann-Whitney p"], rows)
md("Pozn.: dĺžka promptu silne koreluje s veľkosťou triedy, takže ide o asociáciu, nie o kauzálny vplyv dĺžky.", "")

tsucc = {a: {i: tcells[(a, i)]["pass"] for i in ids} for a in T_ARMS}
R["T_stats"] = stats_block("Testing (class pass)", T_ARMS, T_PAIRS, tsucc, ids,
                           EXTRA + [('ft_testing', 'qwen_base'), ('ft_v3_onto', 'onto_project'), ('ft_onto', 'onto_project'), ('ft_onto', 'qwen_base')])

# ================================================================ REFACTORING
ragg = rj(RR / "reports/aggregate.json")
rc = {(c["arm"], c["id"]): c for c in ragg["cells"]}
rids = sorted({c["id"] for c in ragg["cells"]})
acc = {i: rj(RR / "preparation" / i / "accepted.json") for i in rids}
md("## REFACTORING", "", "### R1. Status na rameno × zdroj × typ refaktoringu", "",
   "Skratky: SP = structural_pass, P = passed (SWE overené), CF = checks_failed, IJ = invalid_java, NO = no_op, MOF = model_output_failure.", "")
STAT = ["structural_pass", "passed", "checks_failed", "invalid_java", "no_op", "model_output_failure"]
AB = dict(zip(STAT, ["SP", "P", "CF", "IJ", "NO", "MOF"]))
combos = sorted({(rc[(R_ARMS[0], i)]["source"], rc[(R_ARMS[0], i)]["operation"]) for i in rids})
R["R1"] = {}
rows = []
for s, op in combos:
    sub = [i for i in rids if rc[(R_ARMS[0], i)]["source"] == s and rc[(R_ARMS[0], i)]["operation"] == op]
    r = [s, op, len(sub)]
    for a in R_ARMS:
        c = collections.Counter(rc[(a, i)]["status"] for i in sub)
        R["R1"][f"{a}|{s}|{op}"] = dict(c)
        r.append(" ".join(f"{AB[k]}{c[k]}" for k in STAT if c.get(k)))
    rows.append(r)
table(["zdroj", "operácia", "n"] + R_ARMS, rows)
rows = []
for a in R_ARMS:
    c = collections.Counter(rc[(a, i)]["status"] for i in rids)
    rows.append([a] + [c.get(k, 0) for k in STAT])
md("Súčty:", "")
table(["Rameno"] + [AB[k] for k in STAT], rows)

# ---- R2 checks_failed detail
def ev(a, i):
    p = RR / "cases" / i / "predictions" / a / "evaluation/evaluation.json"
    return rj(p) if p.exists() else None


md("### R2. checks_failed – čo konkrétne zlyhalo", "",
   "Kategórie: *op_missing+iné* = RefactoringMiner nenašiel požadovanú operáciu na cieli, ale našiel iné refaktoringy; "
   "*op_missing+nič* = nenašiel žiadny refaktoring; *op_ok+compile* / *op_ok+test* = operácia sedí, ale SWE build/test zlyhal; "
   "*op_missing+compile/test* = SWE bez operácie a zároveň build/test fail.", "")
R["R2"] = {}
rows = []
det_types = {}
for a in R_ARMS:
    c = collections.Counter()
    dt = collections.Counter()
    for i in rids:
        x = rc[(a, i)]
        if x["status"] != "checks_failed":
            continue
        e = ev(a, i) or {}
        opst = (e.get("operation") or {}).get("status", x["operation_status"])
        evs = (e.get("operation") or {}).get("events") or []
        exe = x["execution_statuses"]
        tag = "op_ok" if opst == "matched" else "op_missing"
        if x["source"] == "swe":
            tag += "+" + ("compile" if "compile_failure" in exe else ("test" if exe and any(s != "passed" for s in exe) else "build_ok"))
        else:
            tag += "+" + ("iné" if evs else "nič")
        c[tag] += 1
        for v in evs:
            dt[v["description"].split("\t")[0]] += 1
    R["R2"][a] = dict(c)
    det_types[a] = dt
    rows.append([a, sum(c.values()), ", ".join(f"{k} {v}" for k, v in c.most_common()),
                 ", ".join(f"{k}×{v}" for k, v in dt.most_common(4))])
table(["Rameno", "CF", "rozpad", "najčastejšie detegované namiesto požadovaného"], rows)

# operation-specific: what was detected instead per requested op (all arms pooled)
md("Pre neúspešné bunky (op_missing, MaRV/ML4Ref): požadovaná operácia → čo RefactoringMiner reálne detegoval (všetky ramená spolu):", "")
rows = []
byop = collections.defaultdict(collections.Counter)
nnone = collections.Counter()
for a in R_ARMS:
    for i in rids:
        x = rc[(a, i)]
        if x["status"] != "checks_failed" or x["source"] == "swe":
            continue
        evs = ((ev(a, i) or {}).get("operation") or {}).get("events") or []
        if not evs:
            nnone[x["operation"]] += 1
        for v in sorted({v["description"].split("\t")[0] for v in evs}):
            byop[x["operation"]][v] += 1
for op in sorted(set(byop) | set(nnone)):
    rows.append([op, nnone[op], ", ".join(f"{k}×{v}" for k, v in byop[op].most_common(4))])
table(["požadovaná", "bez detekcie", "detegované namiesto"], rows)

# ---- R3 discordant
md("### R3. Nesúhlasné prípady (structural success) a preklopenie statusu", "")
R["R3"] = {}
for A, B in R_PAIRS + EXTRA:
    g = [(i, rc[(B, i)]["status"]) for i in rids if rc[(A, i)]["structural_success"] and not rc[(B, i)]["structural_success"]]
    line = [(i, rc[(A, i)]["status"]) for i in rids if rc[(B, i)]["structural_success"] and not rc[(A, i)]["structural_success"]]
    R["R3"][f"{A} vs {B}"] = {"A_only": g, "B_only": line}
    sa = collections.Counter(rc[(A, i)]["source"] + "/" + rc[(A, i)]["operation"] for i, _ in g)
    sb = collections.Counter(rc[(A, i)]["source"] + "/" + rc[(A, i)]["operation"] for i, _ in line)
    md(f"**{A} vs {B}** – A-only {len(g)} (B zlyhalo ako " + ", ".join(f"{k} {v}×" for k, v in collections.Counter(c for _, c in g).most_common()) +
       "; operácie " + ", ".join(f"{k} {v}" for k, v in sa.most_common(4)) + "). "
       f"B-only {len(line)} (A zlyhalo ako " + ", ".join(f"{k} {v}×" for k, v in collections.Counter(c for _, c in line).most_common()) +
       "; operácie " + ", ".join(f"{k} {v}" for k, v in sb.most_common(4)) + ").", "")

# ---- R4 rag_single
md("### R4. rag_single v refaktoringu – prečo no_op a slabší výkon", "")


def gen_code(a, i):
    p = RR / "cases" / i / "predictions" / a / "generated.java"
    return p.read_text(errors="replace") if p.exists() else None


def norm_lines(t):
    return [line.strip() for line in t.splitlines() if line.strip()]


rinfo = {}
for i in rids:
    rp = RR / "cases" / i / "frozen_prompts/rag_single/retrieval.json"
    r = rj(rp)
    sel = r["selection"] if isinstance(r["selection"], dict) else ast.literal_eval(r["selection"])
    docs = sel.get("documents", [])
    content = "\n".join(d.get("content", "") for d in docs)
    metas = []
    for d in docs:
        m = d.get("metadata", {})
        if isinstance(m, str):
            try:
                m = ast.literal_eval(m)
            except Exception:
                m = {}
        metas.append(m)
    before = acc[i]["before"]
    g = gen_code('rag_single', i)
    newl = foreign = 0
    if g:
        bl = set(norm_lines(before))
        cl = set(norm_lines(content))
        nl = [line for line in norm_lines(g) if line not in bl and len(line) > 8]
        newl = len(nl)
        foreign = sum(1 for line in nl if line in cl)
    same_cls = sum(1 for m in metas if m.get("class_name") == acc[i].get("class_name", "").split(".")[-1])
    rinfo[i] = {"n_docs": len(docs), "retrieval_tokens": sel.get("retrieval_tokens"), "scores": [float(d.get("score", 0)) for d in docs],
                "new_lines": newl, "new_lines_from_context": foreign, "same_class_docs": same_cls,
                "types": [str(m.get("refactoring_type", m.get("refactoring_types", "?"))) for m in metas],
                "content": content}
type_match = type_total = type_unknown = case_match = 0
for i in rids:
    ts = re.findall(r"Refactoring type: ([^\n]*)", rinfo[i]["content"])
    type_total += len(ts)
    type_unknown += sum(t.strip() == "unknown" for t in ts)
    k = sum(t.strip() == acc[i]["operation"] for t in ts)
    type_match += k
    case_match += k > 0
nop = [i for i in rids if rc[('rag_single', i)]["status"] == "no_op"]
rows = []
for i in nop:
    x = rc[('rag_single', i)]
    g = gen_code('rag_single', i) or ""
    same = g.strip() == acc[i]["before"].strip()
    sim = difflib.SequenceMatcher(None, acc[i]["before"], g, autojunk=False).ratio() if g and len(g) < 60000 else float('nan')
    rows.append([i[:28], x["source"], x["operation"], x["input_tokens"], rc[('qwen_base', i)]["input_tokens"], x["output_tokens"],
                 rinfo[i]["n_docs"], "áno" if same else f"nie ({sim:.3f})", rc[('qwen_base', i)]["status"]])
R["R4"] = {"no_op_cases": nop, "rinfo": {k: {kk: vv for kk, vv in v.items() if kk != "content"} for k, v in rinfo.items()}}
md("10 no_op buniek rag_single:", "")
table(["prípad", "zdroj", "operácia", "prompt tok rag", "prompt tok base", "output tok", "kontexty", "výstup = vstup?", "qwen_base status"], rows)
pq = [rc[('qwen_base', i)]["input_tokens"] for i in rids]
pr = [rc[('rag_single', i)]["input_tokens"] for i in rids]
cont = sum(1 for i in rids if rinfo[i]["new_lines_from_context"] > 0)
cont_fail = sum(1 for i in rids if rinfo[i]["new_lines_from_context"] > 0 and not rc[('rag_single', i)]["structural_success"])
rows = [["prompt tokeny medián qwen_base → rag_single", f"{st.median(pq):.0f} → {st.median(pr):.0f}"],
        ["prompt tokeny max rag_single", f"{max(pr)}"],
        ["kontextov na prípad", ", ".join(f"{k}:{v}×" for k, v in sorted(collections.Counter(r['n_docs'] for r in rinfo.values()).items()))],
        ["similarity score medián", f"{st.median([s for r in rinfo.values() for s in r['scores']]):.3f}"],
        ["prípady s ≥1 kontextom z rovnakej triedy", f"{sum(1 for r in rinfo.values() if r['same_class_docs'])}/100"],
        ["bunky, kde výstup obsahuje nové riadky doslova z retrieved kontextu (nie zo vstupu)", f"{cont}/100, z toho neúspešných {cont_fail}"],
        ["retrieved príklady s označeným typom = požadovaná operácia", f"{type_match}/{type_total} ({100*type_match/type_total:.0f} %); 'unknown' {type_unknown}"],
        ["prípady s aspoň 1 príkladom požadovaného typu", f"{case_match}/100"]]
table(["Metrika", "Hodnota"], rows)
# by source
rows = []
for s in ["marv", "ml4refactoring", "swe"]:
    sub = [i for i in rids if rc[('rag_single', i)]["source"] == s]
    rows.append([s, len(sub), f"{st.median([rc[('qwen_base', i)]['input_tokens'] for i in sub]):.0f}",
                 f"{st.median([rc[('rag_single', i)]['input_tokens'] for i in sub]):.0f}",
                 sum(rc[('qwen_base', i)]['structural_success'] for i in sub), sum(rc[('rag_single', i)]['structural_success'] for i in sub)])
table(["zdroj", "n", "tok base", "tok rag", "SS base", "SS rag"], rows)

# ---- R5 FT SWE
md("### R5. Prečo FT ramená majú 0/5 na SWE", "")
rows = []
R["R5"] = []
for i in [i for i in rids if rc[('qwen_base', i)]["source"] == "swe"]:
    before = acc[i]["before"]
    for a in ['qwen_base', 'ft_refactoring', 'ft_v3_onto', 'ft_onto']:
        x = rc[(a, i)]
        g = gen_code(a, i) or ""
        meta_p = RR / "cases" / i / "predictions" / a / "generation_metadata.json"
        meta = rj(meta_p) if meta_p.exists() else {}
        same = g.strip() == before.strip()
        sm = difflib.SequenceMatcher(None, before, g, autojunk=False)
        ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
        changed = sum(max(i2 - i1, j2 - j1) for _, i1, i2, j1, j2 in ops)
        rec = dict(case=i[:12], arm=a, op=x["operation"], status=x["status"], in_tok=x["input_tokens"], out_tok=x["output_tokens"],
                   finish=meta.get("finish_reason", meta.get("done_reason")), truncated=meta.get("output_truncated"),
                   max_new=meta.get("max_new_tokens"), identical=same, changed_chars=changed, ratio=sm.ratio())
        R["R5"].append(rec)
        rows.append([rec["case"], a, rec["op"], rec["status"], rec["in_tok"], rec["out_tok"], rec["finish"], rec["truncated"],
                     "áno" if same else "nie", rec["changed_chars"]])
table(["prípad", "rameno", "operácia", "status", "in tok", "out tok", "finish", "truncated", "výstup = vstup", "zmenených znakov"], rows)

# FT no_op elsewhere
rows = []
for a in R_ARMS:
    sub = [i for i in rids if rc[(a, i)]["status"] == "no_op"]
    rows.append([a, len(sub), ", ".join(collections.Counter(rc[(a, i)]["source"] for i in sub).most_common().__repr__().split("),")) if sub else "–"])
md("no_op podľa zdroja:", "")
table(["Rameno", "no_op", "zdroje"], [[a, len([i for i in rids if rc[(a, i)]['status'] == 'no_op']),
                                       ", ".join(f"{k} {v}" for k, v in collections.Counter(rc[(a, i)]['source'] for i in rids if rc[(a, i)]['status'] == 'no_op').most_common())] for a in R_ARMS])

rsucc = {a: {i: bool(rc[(a, i)]["structural_success"]) for i in rids} for a in R_ARMS}
R["R_stats"] = stats_block("Refactoring (structural success)", R_ARMS, R_PAIRS, rsucc, rids,
                           EXTRA + [('ft_refactoring', 'qwen_base'), ('ft_v3_onto', 'onto_project'), ('ft_onto', 'onto_project'), ('ft_onto', 'qwen_base')])

# ================================================================ examples (data for the report)
EX.append("# Príklady (surové dáta pre T4, T5, R4, R5)\n")
EX.append("## T4 – symbol z ontologického bloku, ktorý nie je v zdroji\n")
for a, i, hit in inv_ex[:6]:
    log = (case_dir[i] / "predictions" / a / "coverage-0/evaluation/compile.log").read_text(errors="replace")
    EX.append(f"### {a} / {i} – symboly {hit}\n\nBlok:\n```\n{block[i][:1200]}\n```\nPrvá chyba:\n```\n" +
              "\n".join(line.split('/evaluation/')[-1] for line in log.splitlines()[:6]) + "\n```\n")
if not inv_ex:
    EX.append("Žiadny prípad – v žiadnej bunke nie je chýbajúci symbol, ktorý by bol v bloku a nie v zdroji. Namiesto toho prípady, kde onto rameno zlyhalo a jeho partner prešiel:\n")
    for A, B in [('onto_project', 'qwen_base'), ('skills_onto', 'skills')]:
        for i in ids:
            if tcells[(B, i)]["pass"] and not tcells[(A, i)]["pass"] and tcells[(A, i)]["cat"].startswith("compile"):
                log = (case_dir[i] / "predictions" / A / "coverage-0/evaluation/compile.log").read_text(errors="replace")
                EX.append(f"### {A} / {i} ({tcells[(A, i)]['cat']}; {B} prešlo)\n\nBlok:\n```\n{block[i][:900]}\n```\nChyba:\n```\n" +
                          "\n".join(line.split('/evaluation/')[-1] for line in log.splitlines()[:5]) + "\n```\n")
EX.append("## T5 – symbol z retrieved kontextu\n")
for i, hit in copied_ex[:4]:
    log = (case_dir[i] / "predictions/rag_single/coverage-0/evaluation/compile.log").read_text(errors="replace")
    snip = []
    for h in hit[:2]:
        k = rag[i]["content"].find(h)
        snip.append(rag[i]["content"][max(0, k - 200):k + 200])
    EX.append(f"### rag_single / {i} – symboly {hit}\n\nÚryvok z retrieved:\n```\n" + "\n...\n".join(snip) + "\n```\nChyba:\n```\n" +
              "\n".join(line.split('/evaluation/')[-1] for line in log.splitlines()[:6]) + "\n```\n")
EX.append("## R4 – rag_single, nové riadky z kontextu\n")
for i in sorted(rids, key=lambda i: -rinfo[i]["new_lines_from_context"])[:3]:
    g = gen_code('rag_single', i) or ""
    bl = set(norm_lines(acc[i]["before"]))
    cl = set(norm_lines(rinfo[i]["content"]))
    nl = [line for line in norm_lines(g) if line not in bl and len(line) > 8 and line in cl]
    EX.append(f"### {i} ({rc[('rag_single', i)]['operation']}, status {rc[('rag_single', i)]['status']}) – "
              f"{rinfo[i]['new_lines_from_context']}/{rinfo[i]['new_lines']} nových riadkov z kontextu\n\n```\n" + "\n".join(nl[:12]) + "\n```\n")
EX.append("## R4 – rag_single no_op: diff vstup→výstup bez prázdnych riadkov\n")
for i in nop[5:8]:
    g = gen_code('rag_single', i) or ""
    nb = [line for line in acc[i]["before"].splitlines() if line.strip()]
    ng = [line for line in g.splitlines() if line.strip()]
    d = list(difflib.unified_diff(nb, ng, "before(bez prázdnych)", "rag_single", n=0, lineterm=""))
    EX.append(f"### {i[:30]} ({acc[i]['operation']}; cieľ: {str(acc[i].get('request'))[:200]})\n\nprompt {rc[('rag_single', i)]['input_tokens']} tok; zmenených neprázdnych riadkov: {sum(1 for line in d if line[:1] in '+-' and not line.startswith(('+++','---')))}\n```diff\n" + "\n".join(d[:16]) + "\n```\n")
EX.append("## R5 – FT výstup na SWE (unified diff vstup→výstup, prvých 40 riadkov)\n")
for i in [i for i in rids if rc[('qwen_base', i)]["source"] == "swe"][:3]:
    for a in ['ft_refactoring']:
        g = gen_code(a, i) or ""
        d = list(difflib.unified_diff(acc[i]["before"].splitlines(), g.splitlines(), "before", a, n=1, lineterm=""))
        EX.append(f"### {a} / {i[:12]} ({rc[(a, i)]['operation']}, {rc[(a, i)]['status']})\n\n```diff\n" + "\n".join(d[:40]) + "\n```\n")

_txt = "\n".join(MD) + "\n"
_summ = resolve_path(ARGS.summary) if ARGS.summary else None
if _summ and _summ.exists():
    _k = _txt.index("## TESTING")
    _txt = _txt[:_k] + _summ.read_text() + _txt[_k:]
(OUT / "results.md").write_text(_txt)
(OUT / "examples.md").write_text("\n".join(EX) + "\n")
(OUT / "results.json").write_text(json.dumps(R, indent=1, default=str, ensure_ascii=False))
print("OK", OUT)
