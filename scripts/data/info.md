# scripts/data

CLI skripty pre dataset pipeline. Slúžia na kontrolu raw dát, prípravu instruction-tuning JSONL súborov a zostavenie finálnych datasetov pre B1/B2 experimenty.

Hlavná opakovateľná logika je v `src/llm_ontology/data/`. Tento priečinok má držať iba spustiteľné vstupy a prehľadné výpisy pre človeka.

## Inspect skripty

- `inspect_methods2test.py`: skontroluje štruktúru `data/raw/methods2test/corpus/json`, spočíta súbory v oficiálnych splitoch `train/eval/test`, vypíše niekoľko ukážok a odhadne filtrovanú veľkosť vzorky. Použi ho pred prípravou Methods2Test datasetu, najmä keď meníš `--context-field`.
- `inspect_marv.py`: načíta `MaRV.json`, vypíše počty podľa refactoring typu, dostupné polia a prvý záznam. Použi ho na rýchle overenie, že raw MaRV súbor má očakávaný tvar.
- `inspect_ml4refactoring.py`: skontroluje ML4Refactoring ZIP štruktúru, prvé ZIPy, vybraný projekt, počty commit adresárov a ukážkové názvy Java súborov. Používa dočasné rozbalenie cez bezpečný extractor; pri veľkom datasete spúšťaj s rozumne nastaveným `--max-projects`.

## Prepare skripty

- `prepare_methods2test.py`: pripraví JUnit test generation dataset do `data/processed/testing`. Číta oficiálne splity Methods2Test, filtruje krátke alebo nepoužiteľné príklady a zachováva metadáta ako `source_file` a `context_level`. Predvolené veľkosti sú 4000/500/500.
- `prepare_marv.py`: pripraví MaRV refactoring dataset zo súboru `MaRV.json`. Robí stratifikovaný split podľa podporovaných refactoring typov a ukladá metadáta ako `refactoring_type`, `commit_sha`, `file_path` a `evaluation_votes`.
- `prepare_ml4refactoring.py`: pripraví ML4Refactoring subset z projektových ZIPov. Páruje `before-refactoring` a `after-refactoring` Java súbory, filtruje príliš krátke/dlhé páry a zapisuje `data/processed/refactoring_ml4ref`. Tento skript môže čítať veľa dát a používa dočasný adresár, preto je vhodné najprv spustiť inspect.
- `prepare_final_datasets.py`: zostaví finálne datasety pre experimenty. `refactoring/` vzniká kombináciou ML4Refactoring + MaRV pre B2-R. `combined/` vzniká kombináciou Methods2Test + ML4Refactoring pre B1. Skript zároveň kontroluje očakávané počty a domény.
- `prepare_data.py`: starší všeobecný loader nad `configs/base.yaml`, ktorý vie pripraviť jednoduché refactoring/testing/combined splity z raw priečinkov. Pre aktuálnu experimentálnu pipeline preferuj špecializované skripty vyššie a potom `prepare_final_datasets.py`.

## Typické poradie

```bash
python scripts/data/inspect_methods2test.py
python scripts/data/prepare_methods2test.py

python scripts/data/inspect_ml4refactoring.py
python scripts/data/prepare_ml4refactoring.py

python scripts/data/inspect_marv.py
python scripts/data/prepare_marv.py

python scripts/data/prepare_final_datasets.py
```

Plné `*.jsonl` výstupy v `data/processed/` sú lokálne artefakty a nemajú sa commitovať.
