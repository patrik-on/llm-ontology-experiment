# configs/shared

Spoločné konfigurácie, ktoré vlastní viac než jedna výskumná oblasť:

- `base.yaml` — základné projektové a datasetové nastavenia,
- `models/` — zdieľané definície modelov pre fine-tuning aj inference,
- `environment/` — reprodukovateľné environment lock súbory.

Konfigurácia špecifická pre jedinú oblasť patrí do jej vlastného priečinka
(`finetuning/`, `retrieval/`, `inference/`, `evaluation/` alebo `experiments/`).
