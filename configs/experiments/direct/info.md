# configs/experiments/direct

Direct experimenty predstavujú hlavný promptovaný baseline bez retrieval
kontextu. `qwen25_coder_7b.yaml` používa Qwen2.5-Coder-7B-Instruct a
deterministické generovanie.

Direct výsledky sa porovnávajú s RAG a multi-RAG nad rovnakým modelom,
rovnakými testovacími príkladmi a rovnakým output kontraktom.
