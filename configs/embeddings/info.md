# Embedding providers

`ollama_bge_m3.yaml` is the current standalone WSL Ollama embedding-provider
configuration (`bge-m3`, dimension 1024, fixed localhost endpoint).
The executable RAG configuration using the same values is
`configs/retrieval/ollama_bge_m3.yaml`. The Jina/Sentence Transformers baseline
remains available independently for legacy comparison, not as the current final
baseline.
