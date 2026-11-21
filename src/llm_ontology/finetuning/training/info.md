# src/llm_ontology/finetuning/training

QLoRA training engine a environment readiness kontroly.

- `finetuning.py`: tokenizácia, prompt label masking, Trainer, checkpoints,
  early stopping, resume, final adapter a summary,
- `readiness.py`: model/config/dataset/output validácia (read-only).

Model loading deleguje na `llm_ontology.models`; prompt formatter je zdieľaný
s inferenciou. Training nemení generation approach. Adaptéry hodnotia ramená `ft_*`
v oboch maticiach.
