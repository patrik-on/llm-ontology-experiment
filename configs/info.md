# configs

| Priečinok | Účel | Aktívne súbory |
|---|---|---|
| `benchmarks/` | dve evaluačné matice | `testing_matrix_v1.json`, `refactoring_matrix_v1.json`, `java_evaluation_runtime_v1.yaml` |
| `evaluation/` | modely a Java nástroje pre evaluáciu | `eval_models.yaml`, `jacoco_v1.json`, `methods2test_assertions_v1.json` |
| `retrieval/` | RAG | `ollama_bge_m3_v3.yaml` (jediný aktuálny), `base.yaml` (mock/test) |
| `embeddings/` | samostatný embedding provider | `ollama_bge_m3.yaml` |
| `finetuning/` | LoRA tréning (configy, ktorými vznikli v2 adaptéry) | `lora_config.yaml`, `training_*_wsl.yaml` |
| `shared/` | base config a modely | `base.yaml`, `models/` |
| `skills/` | pinnuté `SKILL.md` pre rameno `skills` | `testing/`, `refactoring/` |
| `datasets/` | spracovanie datasetov a manifesty | |

Číslo verzie v názve (`_v1`, `_v3`) je identita protokolu alebo indexu, nie
alternatíva: v repozitári je vždy iba jedna aktívna verzia. Staršie verzie sú v Git histórii.
Absolútne cesty sa zapisujú ako `${LLM_ONTOLOGY_*}` (pozri `.env.example`).
