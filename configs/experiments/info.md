# configs/experiments

Experiment je kompozícia troch osí:

```text
model variant × generation approach × task
```

- `direct/`: čisté LLM promptovanie bez retrieval kontextu,
- `rag/`: jeden logický retrieval tok,
- `multi_rag/`: viac špecializovaných retrieval zdrojov a fusion.

Fine-tuning configy zostávajú v `configs/finetuning/`, pretože menia váhy
modelu. RAG mení kontext pred generovaním. RAG šablóny majú `enabled: false`,
kým neexistuje train-only index a spustiteľný retrieval runner.
