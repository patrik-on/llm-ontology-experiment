from __future__ import annotations


EXPERIMENTS = {
    "testing": "configs/finetuning/training_b2_testing_wsl.yaml",
    "refactoring": "configs/finetuning/training_b2_refactoring_wsl.yaml",
}
TRAIN_SIZES = (500, 1000, 2000, 4000)
SEEDS = (42, 43, 44)
OUTPUT_ROOT = "/home/patrik/experiments/llm-ontology/size_ablation"


def main() -> None:
    for task, config in EXPERIMENTS.items():
        for train_size in TRAIN_SIZES:
            for seed in SEEDS:
                run_name = f"{task}_n{train_size}_seed{seed}"
                print(
                    "python scripts/training/train_finetuning.py "
                    f"--config {config} "
                    f"--max_train_samples {train_size} "
                    f"--seed {seed} "
                    f"--output-root {OUTPUT_ROOT}/{run_name}"
                )


if __name__ == "__main__":
    main()
