from __future__ import annotations

import hashlib
import importlib.metadata
import re
from dataclasses import dataclass
from typing import Any, Iterable

from pydantic import BaseModel, Field

from llm_ontology.retrieval.models import DocumentChunk, SourceDocument, make_document_chunk


TYPE_NODES = {
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
    "annotation_type_declaration",
}
METHOD_NODES = {"method_declaration", "constructor_declaration"}


class JavaMethod(BaseModel):
    content: str
    package_name: str = ""
    imports: list[str] = Field(default_factory=list)
    class_name: str = ""
    class_declaration: str = ""
    method_name: str = ""
    method_signature: str = ""
    return_type: str = ""
    parameter_types: list[str] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list)
    start_line: int
    end_line: int
    synthetic_wrapper: bool = False


class JavaParseResult(BaseModel):
    parser: str = "tree-sitter-java"
    parser_version: str
    grammar_version: str
    parse_success: bool
    methods: list[JavaMethod] = Field(default_factory=list)
    failure_reason: str = ""


class JavaParser:
    """Pinned Tree-sitter Java parser with a documented method-snippet wrapper."""

    def __init__(self) -> None:
        try:
            from tree_sitter import Language, Parser
            import tree_sitter_java
        except ImportError as exc:  # pragma: no cover - optional installation path.
            raise RuntimeError(
                "Java parsing requires the rag extra with tree-sitter and tree-sitter-java."
            ) from exc
        self.language = Language(tree_sitter_java.language())
        self.parser = Parser(self.language)
        self.parser_version = importlib.metadata.version("tree-sitter")
        self.grammar_version = importlib.metadata.version("tree-sitter-java")

    def parse(self, source: str, *, allow_method_wrapper: bool = False) -> JavaParseResult:
        direct = self._parse_compilation_unit(source, synthetic_wrapper=False, line_offset=0)
        if direct.parse_success and direct.methods:
            return direct
        if allow_method_wrapper:
            wrapped = "class __RagSynthetic__ {" + chr(10) + source + chr(10) + "}"
            wrapped_result = self._parse_compilation_unit(
                wrapped,
                synthetic_wrapper=True,
                line_offset=1,
            )
            if wrapped_result.parse_success and wrapped_result.methods:
                return wrapped_result
        return direct

    def _parse_compilation_unit(
        self,
        source: str,
        *,
        synthetic_wrapper: bool,
        line_offset: int,
    ) -> JavaParseResult:
        source_bytes = source.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        root = tree.root_node
        if root.has_error:
            return self._failure("Tree-sitter reported syntax errors.")

        package_node = _first_descendant(root, "package_declaration")
        package_text = _node_text(package_node, source_bytes) if package_node else ""
        package_name = _package_name(package_text)
        import_nodes = _descendants(root, {"import_declaration"})
        imports = [_node_text(node, source_bytes).strip() for node in import_nodes]
        methods: list[JavaMethod] = []
        for type_node in _descendants(root, TYPE_NODES):
            methods.extend(
                self._methods_for_type(
                    type_node,
                    source,
                    source_bytes,
                    package_text,
                    package_name,
                    imports,
                    synthetic_wrapper,
                    line_offset,
                )
            )
        return JavaParseResult(
            parser_version=self.parser_version,
            grammar_version=self.grammar_version,
            parse_success=True,
            methods=methods,
        )

    def _methods_for_type(
        self,
        type_node: Any,
        source: str,
        source_bytes: bytes,
        package_text: str,
        package_name: str,
        imports: list[str],
        synthetic_wrapper: bool,
        line_offset: int,
    ) -> list[JavaMethod]:
        body = type_node.child_by_field_name("body")
        name_node = type_node.child_by_field_name("name")
        if body is None or name_node is None:
            return []
        class_name = _node_text(name_node, source_bytes)
        class_declaration = source_bytes[type_node.start_byte : body.start_byte].decode(
            "utf-8", errors="replace"
        ).strip()
        fields = [
            _node_text(child, source_bytes).strip()
            for child in body.named_children
            if child.type in {"field_declaration", "constant_declaration"}
        ]
        method_nodes = list(_direct_type_methods(body))
        methods = []
        for node in method_nodes:
            name = node.child_by_field_name("name")
            method_name = _node_text(name, source_bytes) if name else ""
            return_node = node.child_by_field_name("type")
            return_type = _node_text(return_node, source_bytes) if return_node else ""
            parameters_node = node.child_by_field_name("parameters")
            parameter_types = _parameter_types(parameters_node, source_bytes)
            method_body = node.child_by_field_name("body")
            signature_end = method_body.start_byte if method_body else node.end_byte
            signature = source_bytes[node.start_byte : signature_end].decode(
                "utf-8", errors="replace"
            ).strip()
            annotations = re.findall(r"@[A-Za-z_$][A-Za-z0-9_$.]*", signature)
            method_text = _node_text(node, source_bytes).strip()
            leading_comment = _leading_comment(source, node.start_point.row)
            declaration_context = [part for part in (package_text.strip(), *imports) if part]
            declaration_context.append(class_declaration + " {")
            declaration_context.extend(fields)
            if leading_comment:
                declaration_context.append(leading_comment)
            declaration_context.append(method_text)
            declaration_context.append("}")
            start_line = max(1, node.start_point.row + 1 - line_offset)
            end_line = max(start_line, node.end_point.row + 1 - line_offset)
            methods.append(
                JavaMethod(
                    content="\n".join(declaration_context),
                    package_name=package_name,
                    imports=imports,
                    class_name="" if synthetic_wrapper else class_name,
                    class_declaration="" if synthetic_wrapper else class_declaration,
                    method_name=method_name,
                    method_signature=signature,
                    return_type=return_type,
                    parameter_types=parameter_types,
                    annotations=annotations,
                    start_line=start_line,
                    end_line=end_line,
                    synthetic_wrapper=synthetic_wrapper,
                )
            )
        return methods

    def _failure(self, reason: str) -> JavaParseResult:
        return JavaParseResult(
            parser_version=self.parser_version,
            grammar_version=self.grammar_version,
            parse_success=False,
            failure_reason=reason,
        )


class JavaAwareChunker:
    """Produce method-level Java chunks and auditable whole-document fallbacks."""

    def __init__(self, pipeline_version: str = "rag-v2", parser: JavaParser | None = None) -> None:
        self.pipeline_version = pipeline_version
        self.parser = parser or JavaParser()

    def chunk(self, document: SourceDocument) -> Iterable[DocumentChunk]:
        result = self.parser.parse(document.content, allow_method_wrapper=False)
        parent_id = hashlib.sha256(
            f"{document.source_uri}|{document.content}".encode("utf-8")
        ).hexdigest()
        if not result.parse_success or not result.methods:
            reason = result.failure_reason or "No method or constructor declaration found."
            yield make_document_chunk(
                document,
                metadata={
                    "parser": result.parser,
                    "parser_version": result.parser_version,
                    "grammar_version": result.grammar_version,
                    "parse_success": False,
                    "parse_failure_reason": reason,
                    "chunk_type": "whole_document_fallback",
                    "parent_document_id": parent_id,
                },
                pipeline_version=self.pipeline_version,
            )
            return

        for index, method in enumerate(result.methods):
            yield make_document_chunk(
                document,
                content=method.content,
                embedding_text=method.content,
                chunk_index=index,
                metadata={
                    "parser": result.parser,
                    "parser_version": result.parser_version,
                    "grammar_version": result.grammar_version,
                    "parse_success": True,
                    "chunk_type": "constructor" if not method.return_type else "method",
                    "package_name": method.package_name,
                    "class_name": method.class_name,
                    "method_name": method.method_name,
                    "method_signature": method.method_signature,
                    "return_type": method.return_type,
                    "parameter_types": method.parameter_types,
                    "annotations": method.annotations,
                    "start_line": method.start_line,
                    "end_line": method.end_line,
                    "parent_document_id": parent_id,
                },
                pipeline_version=self.pipeline_version,
            )


class PairAwareJavaChunker:
    """Enrich paired examples with syntax metadata without separating either side."""

    def __init__(self, pipeline_version: str = "rag-v2", parser: JavaParser | None = None) -> None:
        self.pipeline_version = pipeline_version
        self.parser = parser or JavaParser()

    def chunk(self, document: SourceDocument) -> Iterable[DocumentChunk]:
        input_code = str(document.metadata.get("_input_code", ""))
        output_code = str(document.metadata.get("_output_code", ""))
        input_result = self.parser.parse(input_code, allow_method_wrapper=True)
        output_result = self.parser.parse(output_code, allow_method_wrapper=True)
        input_method = input_result.methods[0] if input_result.methods else None
        output_method = output_result.methods[0] if output_result.methods else None
        parse_success = input_method is not None and output_method is not None
        pair_kind = (
            "refactoring_pair"
            if "refactoring_pair_id" in document.metadata
            else "production_test_pair"
        )
        failure_parts = [
            result.failure_reason or "No method found."
            for result, method in ((input_result, input_method), (output_result, output_method))
            if method is None
        ]
        method_metadata = _method_metadata(input_method) if input_method else {}
        yield make_document_chunk(
            document,
            metadata={
                "parser": input_result.parser,
                "parser_version": input_result.parser_version,
                "grammar_version": input_result.grammar_version,
                "parse_success": parse_success,
                "parse_failure_reason": " ".join(failure_parts),
                "chunk_type": pair_kind if parse_success else f"{pair_kind}_fallback",
                **method_metadata,
            },
            pipeline_version=self.pipeline_version,
        )


def _method_metadata(method: JavaMethod) -> dict[str, Any]:
    return {
        "package_name": method.package_name,
        "class_name": method.class_name,
        "method_name": method.method_name,
        "method_signature": method.method_signature,
        "return_type": method.return_type,
        "parameter_types": method.parameter_types,
        "annotations": method.annotations,
        "start_line": method.start_line,
        "end_line": method.end_line,
        "synthetic_wrapper": method.synthetic_wrapper,
    }


def _node_text(node: Any, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _descendants(node: Any, node_types: set[str]) -> list[Any]:
    found = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in node_types:
            found.append(current)
        stack.extend(reversed(current.named_children))
    return found


def _first_descendant(node: Any, node_type: str) -> Any | None:
    matches = _descendants(node, {node_type})
    return matches[0] if matches else None


def _direct_type_methods(body: Any) -> Iterable[Any]:
    stack = list(reversed(body.named_children))
    while stack:
        node = stack.pop()
        if node.type in METHOD_NODES:
            yield node
            continue
        if node.type in TYPE_NODES:
            continue
        stack.extend(reversed(node.named_children))


def _parameter_types(parameters_node: Any | None, source_bytes: bytes) -> list[str]:
    if parameters_node is None:
        return []
    types = []
    for parameter in parameters_node.named_children:
        if parameter.type not in {"formal_parameter", "spread_parameter", "receiver_parameter"}:
            continue
        type_node = parameter.child_by_field_name("type")
        if type_node is not None:
            types.append(_node_text(type_node, source_bytes))
    return types


def _package_name(package_text: str) -> str:
    match = re.search(r"\bpackage\s+([A-Za-z_$][A-Za-z0-9_$.]*)", package_text)
    return match.group(1) if match else ""


def _leading_comment(source: str, start_row: int) -> str:
    lines = source.splitlines()
    cursor = start_row - 1
    collected: list[str] = []
    in_block = False
    while cursor >= 0:
        stripped = lines[cursor].strip()
        if not stripped:
            break
        if stripped.endswith("*/"):
            in_block = True
        if in_block or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            collected.append(lines[cursor])
            if stripped.startswith("/*"):
                in_block = False
            cursor -= 1
            continue
        break
    return "\n".join(reversed(collected)).strip()
