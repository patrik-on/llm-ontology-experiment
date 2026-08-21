# artifacts

Malé projektové artefakty a placeholder adresáre.

- `finetuning/adapters/`: manifesty a SHA-256 checksumy adapter balíkov,
- `finetuning/checkpoints/`: placeholder; reálne checkpointy sú mimo Gitu,
- `retrieval/indexes/`: placeholder a lokálne auditné výstupy index buildera.
- `evaluation/runs/<run_id>/`: canonical lokálne prediction, metrics, report a
  analysis artefakty; každý run obsahuje `run_manifest.json`.

Modelové váhy, adapter ZIP súbory, checkpointy a retrieval indexy sa
necommitujú. Commitovateľné sú iba malé textové manifesty, checksumy,
dokumentácia a `.gitkeep` súbory.
