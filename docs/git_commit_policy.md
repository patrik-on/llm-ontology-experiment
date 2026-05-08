# Git Commit Policy

Tento dokument určuje, čo sa má commitovať a čo má zostať mimo repozitára.

## Commitovať

Zdrojový kód:

- `src/**/*.py`
- `scripts/**/*.py`
- `tests/**/*.py`

Konfigurácie:

- `configs/**/*.yaml`
- training/evaluation/model configy,
- malé šablóny a dataset configy.

Dokumentácia:

- `README.md`
- `docs/**/*.md`
- `**/info.md`

Projektové metadáta:

- `.gitignore`
- `requirements.txt`
- `pyproject.toml`

Malé placeholdery:

- `.gitkeep`, ak držia prázdnu adresárovú štruktúru.

## Necommitovať

Virtuálne prostredia:

- `.venv/`
- `.venv_wsl/`
- `.venv312/`
- `venv/`

Modely a váhy:

- `*.safetensors`
- `*.bin`
- `*.pt`
- `*.gguf`
- `models/`
- `C:/models/`

Dáta:

- `data/raw/**`
- `data/processed/**/*.jsonl`
- `data/external/**`

Výnimka: malé `info.md` súbory v dataset priečinkoch sa môžu commitovať ako dokumentácia.

Tréningové artefakty:

- `experiments/**/checkpoints/`
- `experiments/**/logs/`
- `experiments/**/results/*` okrem `.gitkeep`
- WSL výstupy v `/home/patrik/experiments/llm-ontology`

Evaluation výstupy:

- `evaluation/predictions/**`
- `evaluation/metrics/**`
- `evaluation/reports/**`
- `evaluation/samples/**`
- `evaluation_smoke/**`

Výnimka: `info.md` súbory v `evaluation/` sa môžu commitovať.

Cache a dočasné súbory:

- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `wandb/`
- `runs/`
- `*.log`

## Odporúčaný postup pred commitom

1. Skontroluj stav:

```bash
git status --short
```

2. Skontroluj, či sa nezobrazujú veľké dáta alebo virtuálne prostredia.

3. Ak chceš vidieť ignorované súbory:

```bash
git status --short --ignored
```

4. Commituj hlavne zdrojový kód, configy a dokumentáciu.

Typický commit pre aktuálnu fázu má obsahovať:

- `.gitignore`
- `README.md`
- `docs/*.md`
- `configs/**/*.yaml`
- `scripts/*.py`
- `src/**/*.py`
- `**/info.md`
- `requirements.txt`

