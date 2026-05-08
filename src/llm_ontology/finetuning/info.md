# src/llm_ontology/finetuning

Pomocný kód pre fine-tuning.

- `prompt_formatter.py`: tréningový a inferenčný instruction prompt formát,
- `dataset_loader.py`: načítanie a validácia JSONL instruction datasetov,
- `model_loader.py`: skeleton/loadery pre Hugging Face model, tokenizer a LoRA.

Hlavný tréningový beh riadi `scripts/train_finetuning.py`.
