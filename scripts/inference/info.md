# scripts/inference

CLI skripty pre inferenciu mimo hlavnej HF/LoRA evaluation pipeline.

Na porovnávanie baseline a fine-tuned modelov používaj primárne `scripts/evaluation/run_inference_eval.py`. Tento priečinok ostáva najmä pre Ollama baseline, model setup kontroly a legacy navigáciu.

## Skripty

- `check_model_setup.py`: skontroluje lokálny Hugging Face model a dostupnosť Ollama podľa inference configu. Je užitočný pred baseline/prompt testovaním, keď chceš vedieť, či cesty k modelu a lokálna služba existujú.
- `run_ollama_baseline.py`: spustí limitovaný C0 baseline cez Ollama API. Číta `configs/inference/ollama_qwen25_coder_baseline.yaml`, prejde zadané datasety, vytvorí prompt cez rovnaký formatter a uloží JSONL predikcie. Tento tok je vhodný na rýchle prompt testovanie, nie na fine-tuning.
- `generate.py`: legacy wrapper pre odstránený generic `experiment.yaml` flow. Na nové experimenty ho nepoužívaj; iba vypíše odkaz na aktuálny `scripts/evaluation/run_inference_eval.py`.

## Kedy použiť tento priečinok

Použi `scripts/inference/` vtedy, keď chceš:

- overiť, že lokálny model alebo Ollama baseline sú dostupné,
- rýchlo otestovať promptovanie cez Ollama,
- zachovať starý príkaz s jasnou chybovou hláškou.

Nepoužívaj ho na hlavné porovnanie B1/B2/C0 výsledkov. Na to slúži `scripts/evaluation/`.
