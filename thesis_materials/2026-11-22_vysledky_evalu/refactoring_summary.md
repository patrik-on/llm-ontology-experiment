# Refactoring matrix

| Arm | Calls | Structural success | SWE project verified |
|---|---:|---:|---:|
| qwen_base | 100 | 60/100 | 1/5 |
| onto_project | 100 | 55/100 | 1/5 |
| skills | 100 | 49/100 | 1/5 |
| skills_onto | 100 | 54/100 | 1/5 |
| rag_single | 100 | 37/100 | 0/5 |
| ft_refactoring | 100 | 68/100 | 0/5 |
| ft_v3_onto | 100 | 67/100 | 0/5 |
| ft_onto | 100 | 67/100 | 0/5 |

| Arm | Source | Operation | Structural success |
|---|---|---|---:|
| qwen_base | marv | Extract Method | 3/9 |
| qwen_base | marv | Remove Parameter | 5/8 |
| qwen_base | marv | Rename Method | 7/9 |
| qwen_base | marv | Rename Variable | 9/9 |
| qwen_base | ml4refactoring | Extract Variable | 4/10 |
| qwen_base | ml4refactoring | Inline Variable | 5/10 |
| qwen_base | ml4refactoring | Parameterize Variable | 1/10 |
| qwen_base | ml4refactoring | Rename Class | 9/10 |
| qwen_base | ml4refactoring | Rename Parameter | 9/10 |
| qwen_base | ml4refactoring | Replace Variable With Attribute | 5/10 |
| qwen_base | swe | Extract Method | 3/4 |
| qwen_base | swe | Inline Method | 0/1 |
| onto_project | marv | Extract Method | 2/9 |
| onto_project | marv | Remove Parameter | 5/8 |
| onto_project | marv | Rename Method | 8/9 |
| onto_project | marv | Rename Variable | 6/9 |
| onto_project | ml4refactoring | Extract Variable | 4/10 |
| onto_project | ml4refactoring | Inline Variable | 3/10 |
| onto_project | ml4refactoring | Parameterize Variable | 1/10 |
| onto_project | ml4refactoring | Rename Class | 9/10 |
| onto_project | ml4refactoring | Rename Parameter | 9/10 |
| onto_project | ml4refactoring | Replace Variable With Attribute | 4/10 |
| onto_project | swe | Extract Method | 4/4 |
| onto_project | swe | Inline Method | 0/1 |
| skills | marv | Extract Method | 1/9 |
| skills | marv | Remove Parameter | 3/8 |
| skills | marv | Rename Method | 6/9 |
| skills | marv | Rename Variable | 6/9 |
| skills | ml4refactoring | Extract Variable | 2/10 |
| skills | ml4refactoring | Inline Variable | 2/10 |
| skills | ml4refactoring | Parameterize Variable | 2/10 |
| skills | ml4refactoring | Rename Class | 10/10 |
| skills | ml4refactoring | Rename Parameter | 9/10 |
| skills | ml4refactoring | Replace Variable With Attribute | 4/10 |
| skills | swe | Extract Method | 4/4 |
| skills | swe | Inline Method | 0/1 |
| skills_onto | marv | Extract Method | 2/9 |
| skills_onto | marv | Remove Parameter | 5/8 |
| skills_onto | marv | Rename Method | 6/9 |
| skills_onto | marv | Rename Variable | 8/9 |
| skills_onto | ml4refactoring | Extract Variable | 3/10 |
| skills_onto | ml4refactoring | Inline Variable | 4/10 |
| skills_onto | ml4refactoring | Parameterize Variable | 0/10 |
| skills_onto | ml4refactoring | Rename Class | 10/10 |
| skills_onto | ml4refactoring | Rename Parameter | 9/10 |
| skills_onto | ml4refactoring | Replace Variable With Attribute | 3/10 |
| skills_onto | swe | Extract Method | 4/4 |
| skills_onto | swe | Inline Method | 0/1 |
| rag_single | marv | Extract Method | 0/9 |
| rag_single | marv | Remove Parameter | 3/8 |
| rag_single | marv | Rename Method | 6/9 |
| rag_single | marv | Rename Variable | 6/9 |
| rag_single | ml4refactoring | Extract Variable | 1/10 |
| rag_single | ml4refactoring | Inline Variable | 2/10 |
| rag_single | ml4refactoring | Parameterize Variable | 0/10 |
| rag_single | ml4refactoring | Rename Class | 10/10 |
| rag_single | ml4refactoring | Rename Parameter | 7/10 |
| rag_single | ml4refactoring | Replace Variable With Attribute | 2/10 |
| rag_single | swe | Extract Method | 0/4 |
| rag_single | swe | Inline Method | 0/1 |
| ft_refactoring | marv | Extract Method | 4/9 |
| ft_refactoring | marv | Remove Parameter | 4/8 |
| ft_refactoring | marv | Rename Method | 8/9 |
| ft_refactoring | marv | Rename Variable | 9/9 |
| ft_refactoring | ml4refactoring | Extract Variable | 7/10 |
| ft_refactoring | ml4refactoring | Inline Variable | 7/10 |
| ft_refactoring | ml4refactoring | Parameterize Variable | 5/10 |
| ft_refactoring | ml4refactoring | Rename Class | 9/10 |
| ft_refactoring | ml4refactoring | Rename Parameter | 10/10 |
| ft_refactoring | ml4refactoring | Replace Variable With Attribute | 5/10 |
| ft_refactoring | swe | Extract Method | 0/4 |
| ft_refactoring | swe | Inline Method | 0/1 |
| ft_v3_onto | marv | Extract Method | 5/9 |
| ft_v3_onto | marv | Remove Parameter | 4/8 |
| ft_v3_onto | marv | Rename Method | 6/9 |
| ft_v3_onto | marv | Rename Variable | 9/9 |
| ft_v3_onto | ml4refactoring | Extract Variable | 7/10 |
| ft_v3_onto | ml4refactoring | Inline Variable | 5/10 |
| ft_v3_onto | ml4refactoring | Parameterize Variable | 7/10 |
| ft_v3_onto | ml4refactoring | Rename Class | 9/10 |
| ft_v3_onto | ml4refactoring | Rename Parameter | 10/10 |
| ft_v3_onto | ml4refactoring | Replace Variable With Attribute | 5/10 |
| ft_v3_onto | swe | Extract Method | 0/4 |
| ft_v3_onto | swe | Inline Method | 0/1 |
| ft_onto | marv | Extract Method | 5/9 |
| ft_onto | marv | Remove Parameter | 4/8 |
| ft_onto | marv | Rename Method | 7/9 |
| ft_onto | marv | Rename Variable | 9/9 |
| ft_onto | ml4refactoring | Extract Variable | 6/10 |
| ft_onto | ml4refactoring | Inline Variable | 7/10 |
| ft_onto | ml4refactoring | Parameterize Variable | 6/10 |
| ft_onto | ml4refactoring | Rename Class | 9/10 |
| ft_onto | ml4refactoring | Rename Parameter | 10/10 |
| ft_onto | ml4refactoring | Replace Variable With Attribute | 4/10 |
| ft_onto | swe | Extract Method | 0/4 |
| ft_onto | swe | Inline Method | 0/1 |

## Primary pairs: structural success (exact McNemar, Holm across the predeclared pairs)

| Pair (A vs B) | Both | A only | B only | Neither | Unresolved | Δ A−B (pp) | p | p Holm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| onto_project vs qwen_base | 50 | 5 | 10 | 35 | 0 | -5.0 | 0.3018 | 1.0000 |
| ft_v3_onto vs ft_refactoring | 62 | 5 | 6 | 27 | 0 | -1.0 | 1.0000 | 1.0000 |
| ft_onto vs ft_v3_onto | 61 | 6 | 6 | 27 | 0 | +0.0 | 1.0000 | 1.0000 |
| skills_onto vs skills | 43 | 11 | 6 | 40 | 0 | +5.0 | 0.3323 | 1.0000 |
| skills_onto vs onto_project | 49 | 5 | 6 | 40 | 0 | -1.0 | 1.0000 | 1.0000 |

Pending/infra failures are not passes; all planned cells remain in denominators.
Passing checks is not proof of full behavioral equivalence.
Systems comparison: Ollama Q4_K_M structured JSON versus HF PEFT NF4 raw instruction. Primary pairs differ in one input on the same backend; cross-backend pairs are descriptive only.
Fixed source/type quotas and deterministic convenience selection. MaRV/ML4Ref contextual units score only the requested operation and target; other changes are unscored and no project builds/tests are implied. SWE is separately build/test filtered. Basic lexical/commit overlap screen only, not certified unseen, clone-free or independent commits. Structural success is not behavioral equivalence. Builds/tests apply only to the separately reported SWE project subset.
