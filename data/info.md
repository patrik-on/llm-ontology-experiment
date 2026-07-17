# data

Lokálne datasety a malé dokumentačné ukážky.

| Priečinok | Obsah | Git |
|---|---|---|
| `raw/` | pôvodné stiahnuté datasety | ignorované okrem dokumentácie |
| `processed/` | train/val/test JSONL pre tréning a evaluáciu | JSONL ignorované |
| `samples/` | malé ukážky schémy | commitované |
| `external/` | doplnkové externé zdroje | ignorované |

Tréning ani evaluácia nesmú meniť processed datasety. Budúci RAG corpus builder
číta iba train splity a zapisuje indexy mimo dataset priečinkov.
