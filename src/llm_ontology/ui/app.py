from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from llm_ontology.core.logging import setup_logging
from llm_ontology.ui.models import (
    MODE_LABELS,
    TASK_LABELS,
    EnvironmentStatus,
    UIRunView,
)
from llm_ontology.ui.service import UIService, create_ui_service

RETRIEVAL_HEADERS = [
    "rank",
    "document_id",
    "collection",
    "source_type",
    "dataset_name",
    "score",
    "class_name",
    "method_name",
    "source_path",
    "used_in_prompt",
    "preview",
]

COLLECTION_HEADERS = [
    "name",
    "document_count",
    "embedding_model",
    "embedding_revision",
    "chunker_version",
    "manifest_status",
]


def _gradio():
    try:
        import gradio as gr
    except ImportError as exc:  # pragma: no cover - optional UI dependency.
        raise RuntimeError(
            'Gradio is not installed. Run: python -m pip install -e ".[ui,rag]"'
        ) from exc
    return gr


def build_app(service: UIService):
    gr = _gradio()
    default_task_label = next(
        label
        for label, task in TASK_LABELS.items()
        if task == service.settings.default_task
    )
    default_mode_label = next(
        label
        for label, mode in MODE_LABELS.items()
        if mode == service.settings.default_mode
    )
    default_collection = service.collection_for_label(
        default_task_label, default_mode_label
    )

    with gr.Blocks(title="LLM Ontology Experiment") as app:
        gr.Markdown(
            "# LLM Ontology Experiment\n"
            "Local manual testing for Direct LLM and the configured RAG pipeline. "
            "MultiRAG remains disabled until the shared runner implements fusion."
        )

        with gr.Row():
            task = gr.Dropdown(
                choices=list(TASK_LABELS),
                value=default_task_label,
                label="Task",
                interactive=True,
            )
            mode = gr.Dropdown(
                choices=list(MODE_LABELS),
                value=default_mode_label,
                label="Mode",
                interactive=True,
            )
            gr.Textbox(
                value=service.model_name,
                label="Configured model",
                interactive=False,
            )

        java_input = gr.Code(
            label="Java Input",
            language=None,
            lines=22,
            interactive=True,
        )
        requirements = gr.Textbox(
            label="Additional Requirements",
            placeholder=(
                "Optional. The configured task instruction is used when this is empty."
            ),
            lines=4,
        )

        with gr.Accordion("Retrieval settings", open=True):
            with gr.Row():
                top_k = gr.Number(
                    value=5,
                    minimum=1,
                    maximum=100,
                    precision=0,
                    label="Top K",
                    interactive=default_mode_label == "RAG",
                )
                collection = gr.Textbox(
                    value=default_collection,
                    label="Configured collection",
                    interactive=False,
                )
                log_level = gr.Dropdown(
                    choices=["INFO", "DEBUG"],
                    value=service.settings.log_level,
                    label="Log level",
                )
            mode_note = gr.Markdown(_mode_note(default_mode_label))

        run_button = gr.Button("Run", variant="primary")
        run_status = gr.Markdown("Ready.")

        with gr.Tabs():
            with gr.Tab("Output"):
                generated_code = gr.Code(
                    label="Generated Java",
                    language=None,
                    lines=20,
                    interactive=False,
                )
                output_details = gr.JSON(label="Structured output details")

            with gr.Tab("Retrieval"):
                retrieval_message = gr.Markdown("Retrieval disabled.")
                retrieval_table = gr.Dataframe(
                    headers=RETRIEVAL_HEADERS,
                    datatype=[
                        "number",
                        "str",
                        "str",
                        "str",
                        "str",
                        "number",
                        "str",
                        "str",
                        "str",
                        "bool",
                        "str",
                    ],
                    interactive=False,
                    wrap=True,
                    label="Retrieval trace",
                )
                retrieval_details = gr.Textbox(
                    label="Retrieved document details",
                    lines=18,
                    interactive=False,
                )

            with gr.Tab("Prompt"):
                final_prompt = gr.Textbox(
                    label="Final prompt sent to the LLM",
                    lines=24,
                    interactive=False,
                )
                prompt_metadata = gr.JSON(label="Prompt metadata")

            with gr.Tab("Metrics"):
                metrics = gr.JSON(label="Technical metrics")

            with gr.Tab("Logs"):
                logs = gr.Textbox(
                    label="Current run logs",
                    lines=24,
                    interactive=False,
                )

            with gr.Tab("Environment"):
                refresh_environment = gr.Button("Refresh status")
                environment = gr.JSON(label="Environment status")
                collections = gr.Dataframe(
                    headers=COLLECTION_HEADERS,
                    interactive=False,
                    wrap=True,
                    label="Collections",
                )

        def update_mode(task_label: str, mode_label: str):
            retrieval_enabled = mode_label == "RAG"
            return (
                gr.update(interactive=retrieval_enabled),
                service.collection_for_label(task_label, mode_label),
                _mode_note(mode_label),
            )

        def update_collection(task_label: str, mode_label: str):
            return service.collection_for_label(task_label, mode_label)

        def run_interactive(
            task_label: str,
            mode_label: str,
            code: str,
            instructions: str,
            requested_top_k: float,
            requested_log_level: str,
        ):
            result = service.run(
                task_label=task_label,
                mode_label=mode_label,
                source_code=code or "",
                requirements=instructions or "",
                top_k=int(requested_top_k or 5),
                log_level=requested_log_level,
            )
            return _render_run(result)

        mode.change(
            fn=update_mode,
            inputs=[task, mode],
            outputs=[top_k, collection, mode_note],
            queue=False,
        )
        task.change(
            fn=update_collection,
            inputs=[task, mode],
            outputs=collection,
            queue=False,
        )
        run_button.click(
            fn=run_interactive,
            inputs=[task, mode, java_input, requirements, top_k, log_level],
            outputs=[
                generated_code,
                output_details,
                retrieval_message,
                retrieval_table,
                retrieval_details,
                final_prompt,
                prompt_metadata,
                metrics,
                logs,
                run_status,
            ],
            concurrency_limit=1,
        )
        refresh_environment.click(
            fn=lambda: _render_environment(service.environment_status()),
            outputs=[environment, collections],
            concurrency_limit=1,
        )

    return app


def _mode_note(mode_label: str) -> str:
    if mode_label == "Direct LLM":
        return "Retrieval is disabled; Top K is ignored."
    if mode_label == "RAG":
        return "The configured single Chroma collection is queried by the shared runner."
    return "MultiRAG is visible for completeness but is not available yet."


def _render_run(view: UIRunView) -> tuple[Any, ...]:
    output_details = view.output.model_dump(exclude={"code"}, mode="json")
    rows = [
        [getattr(document, header) for header in RETRIEVAL_HEADERS]
        for document in view.retrieval_documents
    ]
    details = "\n\n".join(
        f"[{document.rank}] {document.document_id} ({document.collection})\n"
        f"{document.content}"
        for document in view.retrieval_documents
    )
    prompt_metadata = view.prompt.model_dump(
        exclude={"final_prompt"}, mode="json"
    )
    status = (
        f"✅ **{view.status}** — Run ID: `{view.run_id}`"
        if view.success
        else f"❌ **{view.status}:** {view.error}"
    )
    return (
        view.output.code,
        output_details,
        view.retrieval_message,
        rows,
        details,
        view.prompt.final_prompt,
        prompt_metadata,
        view.metrics.values,
        view.logs,
        status,
    )


def _render_environment(status: EnvironmentStatus) -> tuple[dict[str, Any], list[list[Any]]]:
    payload = status.model_dump(exclude={"collections"}, mode="json")
    rows = [
        [getattr(collection, header) for header in COLLECTION_HEADERS]
        for collection in status.collections
    ]
    return payload, rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the local Gradio experiment UI.")
    parser.add_argument("--config", default="configs/ui/local.yaml")
    parser.add_argument("--host", help="Override configured bind host.")
    parser.add_argument("--port", type=int, help="Override configured port.")
    parser.add_argument(
        "--in-browser",
        action="store_true",
        help="Open the local UI in the default browser after launch.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = create_ui_service(Path(args.config))
    setup_logging(service.settings.log_level)
    app = build_app(service)
    app.queue(default_concurrency_limit=1).launch(
        server_name=args.host or service.settings.host,
        server_port=args.port or service.settings.port,
        inbrowser=args.in_browser,
        share=False,
    )
    return 0
