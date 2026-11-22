# artifacts/finetuning/adapters

Checksums of the four v3 LoRA adapters used by the final matrices. The adapter
weights themselves are not in Git; they live in
`~/experiments/llm-ontology-v3/<adapter>/checkpoints/final_adapter`
(paths in `configs/evaluation/eval_models.yaml`).

| Adapter | Matrix arms | Training config | Data | train_runtime | train_loss |
|---|---|---|---|---:|---:|
| `b2_testing` (`b2_testing_v3`) | testing `ft_testing`, `ft_v3_onto` | `configs/finetuning/training_b2_testing_wsl.yaml` | `data/processed/v3/testing` | 15 017 s | 0.512 |
| `b2_testing_onto` | testing `ft_onto` | `configs/finetuning/training_b2_testing_onto_wsl.yaml` | `data/processed/v3_onto/testing` | 14 127 s | 0.512 |
| `b2_refactoring` (`b2_refactoring_v3`) | refactoring `ft_refactoring`, `ft_v3_onto` | `configs/finetuning/training_b2_refactoring_wsl.yaml` | `data/processed/v3/refactoring` | 42 070 s | 0.066 |
| `b2_refactoring_onto` | refactoring `ft_onto` | `configs/finetuning/training_b2_refactoring_onto_wsl.yaml` | `data/processed/v3_onto/refactoring` | 30 804 s | 0.066 |

Runtimes and losses are from the training logs (RTX 3080 Laptop, 16 GB). The
`adapter_model.safetensors` hashes equal those pinned in each run's `hf_identity/`.

Verify a local copy:

```bash
cd ~/experiments/llm-ontology-v3/b2_testing/checkpoints/final_adapter
sha256sum -c ~/llm-ontology-experiment/artifacts/finetuning/adapters/b2_testing.sha256
```
