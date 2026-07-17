# src/llm_ontology/core

Spoločné infraštruktúrne utility:

- `config.py`: YAML loading, fallback parser, deep merge a required keys,
- `paths.py`: project root, relative/absolute paths a output directories,
- `logging.py`: konzistentný console logging.

Core nesmie importovať training, retrieval ani evaluation implementáciu.
Vyššie vrstvy môžu používať core, nie naopak.
