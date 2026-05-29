from __future__ import annotations


OUTPUT_ROOT = "/home/patrik/experiments/llm-ontology-v2"
EXPERIMENTS = (
    ("B2-T v2", "b2_testing", "configs/finetuning/training_b2_testing_wsl.yaml"),
    ("B2-R v2", "b2_refactoring", "configs/finetuning/training_b2_refactoring_wsl.yaml"),
    ("B1 shared v2", "b1_shared", "configs/finetuning/training_b1_shared_wsl.yaml"),
)


def training_command(model_dir: str, config: str) -> str:
    return (
        "python scripts/train_finetuning.py \\\n"
        f"  --config {config} \\\n"
        f"  --output-root {OUTPUT_ROOT}/{model_dir}"
    )


def resume_command(model_dir: str, config: str) -> str:
    return (
        "python scripts/train_finetuning.py \\\n"
        f"  --config {config} \\\n"
        f"  --output-root {OUTPUT_ROOT}/{model_dir} \\\n"
        f"  --resume_from_checkpoint {OUTPUT_ROOT}/{model_dir}/checkpoints/checkpoint-XXX"
    )


def after_run_checks(model_dir: str) -> str:
    return (
        f"cat {OUTPUT_ROOT}/{model_dir}/results/training_summary.json\n"
        f"ls {OUTPUT_ROOT}/{model_dir}/checkpoints/final_adapter"
    )


def main() -> None:
    print("V2 fine-tuning commands")
    print("=======================")
    print("\nPre-flight checks")
    print("-----------------")
    print("python -m compileall -q src scripts tests")
    print("python -m pytest tests")
    print("python scripts/training/debug_prompt_masking.py")
    for _, _, config in EXPERIMENTS:
        print(f"python scripts/check_finetuning_ready.py --config {config}")

    print("\nTraining commands")
    print("-----------------")
    for title, model_dir, config in EXPERIMENTS:
        print(f"\n# {title}")
        print(training_command(model_dir, config))

    print("\nResume examples")
    print("---------------")
    for title, model_dir, config in EXPERIMENTS:
        print(f"\n# {title}")
        print(resume_command(model_dir, config))

    print("\nAfter-run checks")
    print("----------------")
    for title, model_dir, _ in EXPERIMENTS:
        print(f"\n# {title}")
        print(after_run_checks(model_dir))

    print("\nMonitoring")
    print("----------")
    print("watch -n 2 nvidia-smi")


if __name__ == "__main__":
    main()
