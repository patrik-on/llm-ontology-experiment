# src/llm_ontology/training

Aktuálna tréningová infraštruktúra projektu.

- `finetuning.py`: hlavný LoRA/QLoRA tréningový engine používaný cez `scripts/training/train_finetuning.py`.
- `readiness.py`: kontrola pripravenosti konkrétneho training configu.
- `compat.py`: kontrola kompatibility PyTorch/Transformers/bitsandbytes/CUDA.
- `setup_check.py`: staršia všeobecná kontrola fine-tuning infraštruktúry.
- `trainer.py`, `dataset.py`, `callbacks.py`, `sampler.py`: staršia všeobecná tréningová vrstva ponechaná pre kompatibilitu a prípadné budúce zjednotenie.

CLI skript `scripts/training/train_finetuning.py` je už iba tenký wrapper. Skutočná logika načítania configov, datasetov, modelu, LoRA adaptera, Trainer inicializácie, summary handlingu, Ctrl+C handlingu a resume z checkpointu je v `finetuning.py`.

