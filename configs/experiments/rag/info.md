# configs/experiments/rag

Konfigurácie pre jeden zjednotený retrieval tok. Aktuálny `template.yaml` je
zámerne vypnutý a povoľuje iba `train` split.

Pred aktiváciou treba implementovať:

- leakage audit a corpus builder,
- embedding/index backend,
- retrieval trace,
- validation-only ladenie `top_k`,
- spustiteľný experiment runner.
