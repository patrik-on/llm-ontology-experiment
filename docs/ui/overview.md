# Local experiment UI

The Gradio UI is a thin, local control and inspection layer over the existing
experiment runner. It does not implement retrieval, prompt construction,
structured-output parsing, Ollama access, or evaluation logic.

## Installation

Run the UI in the same canonical WSL environment as ingestion, Chroma,
retrieval, generation, and evaluation:

```bash
source .venv_wsl/bin/activate
python -m pip install -e ".[rag,ui]"
python -m llm_ontology.env check
```

The `ui` extra installs Gradio 5.x. The `rag` extra supplies ChromaDB,
embedding, tokenization, and ingestion dependencies. Windows virtualenvs and
Windows Ollama are not valid final-experiment UI runtimes.

## Launch

Start the application from the repository root:

```bash
python -m llm_ontology.ui
```

The default address is `http://127.0.0.1:7860`. The UI never binds to
`0.0.0.0` unless explicitly configured. Host and port can be overridden:

```bash
python -m llm_ontology.ui --host 127.0.0.1 --port 7861 --in-browser
```

Defaults and references to the retrieval/experiment configurations are in
`configs/ui/local.yaml`. Model, embedding provider, Chroma path, collection,
generation settings, and experiment token budgets are loaded from existing
project configurations rather than duplicated in Python UI code.

## Layout

```text
LLM Ontology Experiment

Task       [ Testing ]
Mode       [ Direct LLM ]
Model      [ qwen2.5-coder:7b ] (read-only)

Java Input
+--------------------------------------------------+
| Java method, class, test class, or snippet       |
+--------------------------------------------------+

Additional Requirements
+--------------------------------------------------+
| optional request passed to the PromptBuilder     |
+--------------------------------------------------+

Retrieval settings: Top K, configured collection, log level
[ Run ]

[ Output ] [ Retrieval ] [ Prompt ] [ Metrics ] [ Logs ] [ Environment ]
```

## Modes

- **Direct LLM** maps to `no_rag`. Retrieval is bypassed by the shared runner,
  and Top K is ignored.
- **RAG** maps to `single_collection_rag`. The task-specific `*_mixed.yaml`
  experiment configuration selects the controlled `mixed` collection.
- **MultiRAG** maps to `multi_collection_rag`. The shared runner queries
  `testing_db` and `refactoring_db` in parallel, performs RRF and global token
  selection, and returns the complete fusion trace to the UI.

Interactive runs explicitly reuse disabled controlled-experiment templates as
configuration sources, but enabling an interactive run does not mark a batch
experiment or its datasets as approved. Batch configurations remain disabled.

## Result tabs

- **Output** shows generated Java plus the structured summary, assumptions,
  warnings, smells, and recommended refactorings when supplied by the runner.
- **Retrieval** shows per-collection ranks/scores, source collections, RRF score,
  final rank, dataset/type metadata, previews, full text, and prompt selection.
- **Prompt** shows the exact prompt artifact and its hash, token estimate,
  retrieval tokens, and counting method.
- **Metrics** shows only data returned by the shared runner/provider. Missing
  compilation, test, or validation results are displayed as `N/A`.
- **Logs** captures one request through an isolated in-memory logging handler.
  INFO is the default; DEBUG includes the technical exception trace. Common
  secret/token patterns are redacted.
- **Environment** performs read-only WSL/Ollama/Chroma checks. It shows runtime
  OS, fixed base URL, embedding provider/model/digest/dimension, generation
  provider/model/digest, Python/dependencies, Chroma path, collection counts,
  and sidecar manifest metadata.

Successful interactive runs are appended to
`experiments/results/ui/interactive_runs.jsonl`; exact prompts are stored under
`artifacts/prompts/ui/`. Both locations follow the repository's existing
artifact ignore policy.

## Current limitations

- RAG needs a previously built compatible Chroma `mixed` collection. The UI
  does not create, rebuild, or delete indexes.
- Environment collection status reports a missing manifest when an index was
  created through the phase-1 CLI without the phase-2 lifecycle sidecar.
- Java compilation, tests, JaCoCo, and PIT are shown only when a future shared
  evaluator writes them into the experiment record; the UI does not run them.
- Gradio's code editor does not provide Java syntax highlighting in the pinned
  version, but it preserves multiline code in a monospace editor.
