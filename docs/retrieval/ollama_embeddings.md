# Ollama embeddings for ChromaDB

The existing provider-neutral RAG pipeline uses `bge-m3` through Ollama running
inside WSL. The final-experiment endpoint is fixed to `http://localhost:11434`;
Windows Ollama, host-IP forwarding, discovery, and fallback are forbidden. Jina/Sentence Transformers remains available; select the provider
through configuration and rebuild a collection whenever its provider, model,
digest, or vector dimension changes.

## Prepare Ollama

```bash
ollama pull bge-m3
ollama pull qwen2.5-coder:7b
ollama list
curl http://localhost:11434/api/tags
```

WSL `/api/tags` audit captured on 2026-08-20:

| Model | Runtime digest |
|---|---|
| `bge-m3:latest` | `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab` |
| `qwen2.5-coder:7b` | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |

This is an audit observation, not a substitute for runtime resolution. Every
index build and experiment must store the digest returned by its own WSL
runtime.

The standalone provider values are in
`configs/embeddings/ollama_bge_m3.yaml`. The complete executable RAG setup is
`configs/retrieval/ollama_bge_m3.yaml`:

```yaml
embeddings:
  provider: ollama
  model: bge-m3
  base_url: http://localhost:11434
  batch_size: 16
  timeout_seconds: 120
```

`base_url`, model, batch size, timeout, and an optional expected dimension are
configuration values. The provider obtains the installed digest from
`/api/tags`, embeds through `/api/embed`, and discovers the vector dimension
from the first valid response.

## Production indexes

After installing the RAG dependencies and preparing `bge-m3`, run:

```bash
python scripts/retrieval/build_production_indexes.py
```

The command verifies immutable source manifests, filters every benchmark
identity/code-fingerprint overlap, writes derived retrieval manifests, builds
disjoint `testing_db`/`refactoring_db` plus equivalent `mixed`, and writes an
auditable report under `artifacts/retrieval/indexes/`. Benchmark files are read only for
the audit and are never passed to the production corpus builder.

The 2026-08-20 build contains 5,739 unique vectors in `mixed`, equal to 3,978
in `testing_db` plus 1,761 in `refactoring_db`. No approved literature source
was present, so `literature_db` was not created.

Set `RUN_REAL_OLLAMA_EMBEDDING_TEST=1` to enable the opt-in provider integration
test. Regular tests mock the HTTP boundary and do not require Ollama.

## Lifecycle and UI

Collection sidecar manifests record `embedding_provider`, `embedding_model`,
`embedding_model_digest`, `embedding_dimension`, and `ollama_runtime`. Compatibility validation
rejects a Jina collection when Ollama is configured (and vice versa); rebuilding
is always explicit.

The Environment panel reads provider runtime metadata through the service layer.
With the Ollama retrieval configuration it reports provider, model, digest,
dimension, base URL, and embedding/Ollama readiness. The UI does not embed text
or access Ollama directly.
