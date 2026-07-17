# configs

YAML konfigurácie sú rozdelené podľa nezávislých častí experimentu.

| Priečinok | Účel |
|---|---|
| `models/` | modelové cesty a runtime nastavenia |
| `finetuning/` | LoRA/QLoRA parametre a training runs |
| `experiments/` | kompozície model × approach × task |
| `retrieval/` | spoločné retrieval nastavenia |
| `evaluation/` | modely, datasety a generation parametre evaluácie |
| `inference/` | samostatná Ollama baseline inferencia |
| `datasets/` | dataset-specific spracovanie |
| `templates/` | legacy navigácia na nové experiment configy |

Pre reálny CUDA tréning používaj `configs/finetuning/*_wsl.yaml`. Direct, RAG
a multi-RAG experimenty patria do samostatných podpriečinkov
`configs/experiments/`. RAG šablóny zostávajú vypnuté až do implementácie
retrieval runnera.
