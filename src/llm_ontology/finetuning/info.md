# src/llm_ontology/finetuning

Kompatibilná vrstva pôvodných fine-tuning importov.

- `dataset_loader.py`: načítanie a validácia instruction JSONL,
- `prompt_formatter.py`: re-export `llm_ontology.inference.prompting`,
- `model_loader.py`: re-export `llm_ontology.models`.

Nový kód má používať spoločné modelové a promptovacie moduly. Hlavný training
engine je v `llm_ontology.training.finetuning`. Wrappery sa odstránia až po
migrácii všetkých externých importov a runbookov.
