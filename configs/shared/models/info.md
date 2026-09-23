# configs/shared/models

Modelové konfigurácie. Aktuálny experimentálny runtime je výhradne
`qwen25_coder_7b_ollama.yaml` vo WSL. Hugging Face konfigurácie zostávajú
zachované ako `legacy_not_final` pre historické/fine-tuning použitie a nie sú
finálnym experimentálnym baseline.

- `qwen25_coder_7b_hf.yaml`: Windows cesta k lokálnemu Hugging Face modelu.
- `qwen25_coder_7b_hf_wsl.yaml`: WSL cesta k tomu istému modelu cez `/mnt/c`.
- `qwen25_coder_7b_ollama.yaml`: Ollama baseline model `qwen2.5-coder:7b`.

Modelové váhy sú mimo repozitára a nesmú sa commitovať.
