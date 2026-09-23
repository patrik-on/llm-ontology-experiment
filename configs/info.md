# configs

YAML konfigurácie sú rozdelené podľa nezávislých častí experimentu.

| Priečinok | Účel |
|---|---|
| `shared/` | spoločný base config, modelové cesty a environment lock |
| `embeddings/` | embedding provider/model kontrakty |
| `finetuning/` | LoRA/QLoRA parametre a training runs |
| `experiments/` | kompozície model × approach × task |
| `retrieval/` | spoločné retrieval nastavenia |
| `evaluation/` | modely, datasety a generation parametre evaluácie |
| `inference/` | samostatná Ollama baseline inferencia |
| `datasets/` | dataset-specific spracovanie |
| `benchmarks/` | TestBench a SWE-Refactor kontrakty |
| `ui/` | lokálne Gradio UI nastavenia |

Pre reálny CUDA tréning používaj `configs/finetuning/*_wsl.yaml`. Direct, RAG
a multi-RAG experimenty patria do samostatných podpriečinkov
`configs/experiments/`. Aktuálny final baseline používa WSL, Ollama
`bge-m3`, `qwen2.5-coder:7b` a `configs/retrieval/ollama_bge_m3.yaml`.
Windows, Hugging Face a Jina configy sú zachované iba ako `legacy_not_final`.
