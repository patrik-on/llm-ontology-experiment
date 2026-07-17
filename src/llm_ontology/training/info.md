# src/llm_ontology/training

QLoRA training engine a environment readiness kontroly.

- `finetuning.py`: tokenizácia, prompt label masking, Trainer, checkpoints,
  early stopping, resume, final adapter a summary,
- `readiness.py`: model/config/dataset/output validácia,
- `compat.py`: CUDA, Transformers a collator API kontrola,
- `setup_check.py`: staršia všeobecná setup kontrola.

Model loading deleguje na `llm_ontology.models`; prompt formatter je zdieľaný
s inferenciou. Training nemení generation approach. Natrénovaný adaptér sa dá
neskôr vyhodnotiť s direct, RAG aj multi-RAG kontextom.
