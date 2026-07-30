"""JSON, readable algebraic, and MeTTa serializers."""

from __future__ import annotations

import re

from .models import AlgebraicSpecification


def safe_symbol(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", value.replace("-", "_"))
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def to_readable(specification: AlgebraicSpecification) -> str:
    lines = [
        f"spec {specification.concept.upper()}_{specification.perspective.upper()} =",
        "",
        "  sorts",
    ]
    lines.extend(f"    {item.name}" for item in specification.sorts)
    lines.extend(("", "  ops"))
    for item in specification.operations:
        domain = " * ".join(item.inputs)
        signature = f"{domain} -> {item.output}" if domain else item.output
        lines.append(f"    {item.name} : {signature}")
    lines.extend(("", "  preds"))
    for item in specification.predicates:
        lines.append(f"    {item.name} : {' * '.join(item.arguments)}")
    lines.extend(("", "  axioms"))
    lines.extend(f"    {item.expression}" for item in specification.axioms)
    lines.extend(("", "end"))
    return "\n".join(lines)


def _stv(confidence: float) -> str:
    strength = min(0.98, max(0.35, confidence))
    return f"(stv {strength:.3f} {confidence:.3f})"


def to_metta(specification: AlgebraicSpecification) -> str:
    concept = safe_symbol(specification.concept)
    perspective = safe_symbol(specification.perspective)
    lines: list[str] = []
    for index, item in enumerate(specification.sorts):
        edge = f"hybrid_sort_{concept}_{perspective}_{index}"
        lines.append(
            f"(: {edge} (≞ (has_sort {edge} {concept} {perspective} "
            f"{safe_symbol(item.name)}) {_stv(item.confidence)}))"
        )
    for index, item in enumerate(specification.operations):
        edge = f"hybrid_operation_{concept}_{perspective}_{index}"
        signature = (
            f"(arrow {' '.join(safe_symbol(name) for name in item.inputs)} "
            f"{safe_symbol(item.output)})"
            if item.inputs
            else safe_symbol(item.output)
        )
        lines.append(
            f"(: {edge} (≞ (has_operation {edge} {concept} {perspective} "
            f"{safe_symbol(item.name)}) {_stv(item.confidence)}))"
        )
        lines.append(
            f"(: {edge}_signature (≞ (operation_signature {edge} {signature}) "
            f"{_stv(item.confidence)}))"
        )
    for index, item in enumerate(specification.predicates):
        edge = f"hybrid_predicate_{concept}_{perspective}_{index}"
        predicate = (
            f"({safe_symbol(item.name)} "
            f"{' '.join(safe_symbol(name) for name in item.arguments)})"
        )
        lines.append(
            f"(: {edge} (≞ (has_predicate {edge} {concept} {perspective} "
            f"{predicate}) {_stv(item.confidence)}))"
        )
    for index, item in enumerate(specification.axioms):
        edge = f"hybrid_axiom_{concept}_{perspective}_{index}"
        expression = item.expression.replace("->", "arrow").replace("-", "_")
        lines.append(
            f"(: {edge} (≞ (has_axiom {edge} {concept} {perspective} "
            f"{expression}) {_stv(item.confidence)}))"
        )
    return "\n".join(lines) + "\n"
