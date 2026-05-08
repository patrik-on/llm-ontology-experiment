# scripts

CLI vstupy projektu.

Tento priečinok má obsahovať najmä tenké wrappery, nie hlavnú implementačnú logiku. Knižničný kód je v `src/llm_ontology/`.

Tematické priečinky:

- `data/`: príprava a kontrola datasetov,
- `training/`: fine-tuning a kontroly tréningového setupu,
- `inference/`: baseline/generic inference príkazy,
- `evaluation/`: inference evaluation, metriky, reporty a smoke testy.

Presunutá logika:

- `src/llm_ontology/training/`: QLoRA training engine a kontroly,
- `src/llm_ontology/evaluation/`: HF baseline/LoRA evaluation, metriky a reporty,
- `src/llm_ontology/inference/`: Ollama baseline a inference helpery,
- `src/llm_ontology/data/`: dataset pipeline a finálne B1/B2 dataset mixy.

