# src/llm_ontology/finetuning

Pomocný kód pre fine-tuning.

- `prompt_formatter.py`: tréningový a inferenčný instruction prompt formát,
- `dataset_loader.py`: načítanie a validácia JSONL instruction datasetov,
- `model_loader.py`: loadery pre Hugging Face model, tokenizer a LoRA.

Hlavný tréningový beh je implementovaný v `src/llm_ontology/training/finetuning.py`; `scripts/training/train_finetuning.py` je iba CLI wrapper.

