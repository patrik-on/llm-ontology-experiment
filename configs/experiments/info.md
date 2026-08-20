# configs/experiments

`rag_v2/` contains eight controlled cells: Direct, RAG over `mixed`, MultiRAG
over both specialized collections, and one specialized-store ablation for each
task. Configs remain disabled until a batch run is intentionally approved. The
runner never selects metadata RAG or task routing implicitly.
Their current metadata baseline is WSL Ollama `bge-m3` plus
`qwen2.5-coder:7b`; provider/model digests are resolved and stored at runtime.

Experiment je kompozícia troch osí:

```text
model variant × generation approach × task
```

- `direct/`: čisté LLM promptovanie bez retrieval kontextu,
- `rag/`: jeden logický retrieval tok,
- `multi_rag/`: viac špecializovaných retrieval zdrojov a fusion.

Fine-tuning configy zostávajú v `configs/finetuning/`, pretože menia váhy
modelu. RAG mení kontext pred generovaním. Produkčné train-only indexy aj
spoločný runner existujú; `enabled: false` je ochrana pred náhodným batch behom,
nie stav implementácie.
