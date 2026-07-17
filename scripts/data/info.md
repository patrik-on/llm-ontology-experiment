# scripts/data

CLI nástroje pre kontrolu a prípravu datasetov. Opakovateľná logika je v
`src/llm_ontology/data/`.

## Inspect

- `inspect_methods2test.py`: oficiálne splity, ukážky a filtrované štatistiky,
- `inspect_marv.py`: typy refaktoringu, polia a vzorový záznam,
- `inspect_ml4refactoring.py`: ZIP/projekt/commit štruktúra a kandidátne súbory.

## Prepare

- `prepare_methods2test.py`: testing 4000/500/500,
- `prepare_ml4refactoring.py`: ML4Refactoring 4000/500/500,
- `prepare_marv.py`: stratifikovaný MaRV split,
- `prepare_final_datasets.py`: finálny B2-R a B1 mix,
- `prepare_data.py`: starší generic loader zachovaný pre kompatibilitu.

Odporúčané poradie je inspect → prepare pre každý zdroj → final datasets.
Plné JSONL výstupy sa necommitujú. Budúci RAG corpus builder musí byť oddelený
od tejto prípravy a smie čítať iba hotové train splity.
