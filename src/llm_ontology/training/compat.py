from __future__ import annotations

import inspect


def main() -> None:
    import bitsandbytes  # noqa: F401
    import torch
    import transformers
    from transformers import DataCollatorForSeq2Seq, Trainer

    print(f"torch: {torch.__version__}")
    print(f"transformers: {transformers.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available. Run this check inside CUDA-enabled WSL2/Ubuntu.")

    trainer_params = inspect.signature(Trainer.__init__).parameters
    if "processing_class" not in trainer_params:
        raise SystemExit("Trainer does not accept processing_class. Update transformers or adjust train_finetuning.py.")

    collator_params = inspect.signature(DataCollatorForSeq2Seq.__init__).parameters
    if "tokenizer" not in collator_params:
        raise SystemExit("DataCollatorForSeq2Seq does not accept tokenizer.")
    if "label_pad_token_id" not in collator_params:
        raise SystemExit("DataCollatorForSeq2Seq does not accept label_pad_token_id.")

    print("Transformers compatibility check OK.")


if __name__ == "__main__":
    main()
