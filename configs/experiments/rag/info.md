# configs/experiments/rag

Konfigurácie pre jeden zjednotený retrieval tok. Aktuálny `template.yaml` je
zámerne vypnutý proti náhodnému batch behu a povoľuje iba `train` split.
Leakage audit, produkčný corpus builder, Ollama embedding backend, Chroma
lifecycle, retrieval trace aj spoločný runner sú implementované. Pred baseline
freeze sa smie na validation dátach doladiť iba vopred deklarované `top_k`.
