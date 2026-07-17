# data/processed

Validované JSONL datasety pripravené na tréning a evaluáciu.

| Priečinok | Train/Val/Test | Účel |
|---|---|---|
| `testing/` | 4000/500/500 | Methods2Test, JUnit generation |
| `refactoring_ml4ref/` | 4000/500/500 | ML4Refactoring subset |
| `refactoring_marv/` | 478/100/108 | MaRV refactoring |
| `refactoring/` | 4478/600/608 | finálny B2-R mix |
| `combined/` | 8000/1000/1000 | balanced B1 shared mix |

Plné JSONL súbory sú lokálne a ignorované Gitom. Pre RAG sa indexuje iba
`train.jsonl`; val a test zostávajú mimo indexu. Pred finálnym retrieval
experimentom treba overiť deduplikáciu a project/commit leakage.
