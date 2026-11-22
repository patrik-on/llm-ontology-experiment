# Testing matrix

Protocol: methods2test_systems_ontology_v2

| Arm | Calls | Compiled | Class pass | Focal invoked | Unknown class result |
|---|---:|---:|---:|---:|---:|
| qwen_base | 100/100 | 71 | 22 | 22 | 0 |
| onto_project | 100/100 | 67 | 22 | 22 | 0 |
| skills | 100/100 | 78 | 21 | 21 | 0 |
| skills_onto | 100/100 | 75 | 23 | 23 | 0 |
| rag_single | 100/100 | 60 | 14 | 14 | 0 |
| ft_testing | 100/100 | 72 | 53 | 53 | 0 |
| ft_v3_onto | 100/100 | 72 | 48 | 48 | 0 |
| ft_onto | 100/100 | 69 | 51 | 51 | 0 |

## Primary pairs (exact tests, Holm across the predeclared pairs)

A is the arm with the added context, B its control on the same cases and backend.

| A | B | Class pass A only / B only | Class pass Δ (pp) | p McNemar (Holm) | Method line credit Δ | p Wilcoxon (Holm) |
|---|---|---:|---:|---:|---:|---:|
| onto_project | qwen_base | 6 / 6 | +0.0 | 1.0000 (1.0000) | +0.003 | 0.5522 (1.0000) |
| ft_v3_onto | ft_testing | 5 / 10 | -5.0 | 0.3018 (1.0000) | -0.056 | 0.0959 (0.4797) |
| ft_onto | ft_v3_onto | 7 / 4 | +3.0 | 0.5488 (1.0000) | +0.043 | 0.1019 (0.4797) |
| skills_onto | skills | 8 / 6 | +2.0 | 0.7905 (1.0000) | +0.020 | 0.5745 (1.0000) |
| skills_onto | onto_project | 5 / 4 | +1.0 | 1.0000 (1.0000) | +0.010 | 0.7949 (1.0000) |

## Repeat diagnostics (no scoring change)


Pending/interrupted results are unknown; completed failures keep their existing scoring policy.

Missing/unattempted cells are not passing or measured zero coverage.
Extracted-method validation; no real-bug detection or causal FT claim.
Ontology arms measure automatically derived structured context from the supplied code; FT and Ollama arms are compared only within their backend.
