# Dataset Samples

Tento priečinok obsahuje malé commitovateľné ukážky dátových formátov. Súbory
nie sú súčasťou train, validation ani test splitov a pipeline ich nepoužíva.

Plné lokálne datasety sú v `data/processed/` a zostávajú mimo Gitu.

## Spoločná schéma

Každý instruction-tuning záznam obsahuje minimálne:

```json
{
  "instruction": "úloha pre model",
  "input": "vstupný Java kód",
  "output": "očakávaný Java výstup",
  "domain": "testing alebo refactoring",
  "source": "zdroj datasetu"
}
```

Voliteľné metadata zahŕňajú:

- `project`, `commit_sha`, `file_path`,
- `refactoring_type`, `refactoring_id`,
- `context_level`, `source_file`,
- `evaluation_votes`.

## Súbory

| Súbor | Zdroj | Úloha |
|---|---|---|
| `testing_methods2test_sample.json` | Methods2Test | JUnit test generation |
| `refactoring_ml4ref_sample.json` | ML4Refactoring | Java refactoring |
| `refactoring_marv_sample.json` | MaRV | Java refactoring |

## Použitie pri budúcom RAG

Tieto ukážky slúžia iba na dokumentáciu schémy. RAG corpus builder bude čítať
reálne `train.jsonl` splity a musí zachovať metadata potrebné na audit pôvodu,
deduplikáciu a kontrolu data leakage. Validation a test splity sa nesmú indexovať.
