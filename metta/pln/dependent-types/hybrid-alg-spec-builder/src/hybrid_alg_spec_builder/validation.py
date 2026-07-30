"""Logical and structural acceptance gates for generated specifications."""

from __future__ import annotations

from collections import Counter
import re

from .models import AlgebraicSpecification, ValidationIssue
from .ontology import OntologyRegistry


def validate_specification(
    specification: AlgebraicSpecification,
    ontology: OntologyRegistry,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sort_names = {item.name for item in specification.sorts}
    operation_names = {item.name for item in specification.operations}
    predicate_names = {item.name for item in specification.predicates}
    for name in sorted(operation_names & predicate_names):
        issues.append(ValidationIssue("operation-predicate-name-overlap", name))

    for operation in specification.operations:
        missing = sorted(set((*operation.inputs, operation.output)) - sort_names)
        if missing:
            issues.append(
                ValidationIssue(
                    "undeclared-sort",
                    f"{operation.name}: {', '.join(missing)}",
                )
            )

    for predicate in specification.predicates:
        missing = sorted(set(predicate.arguments) - sort_names)
        if missing:
            issues.append(
                ValidationIssue(
                    "undeclared-sort",
                    f"{predicate.name}: {', '.join(missing)}",
                )
            )

    for axiom in specification.axioms:
        missing = sorted(set(axiom.referenced_operations) - operation_names)
        if missing:
            issues.append(
                ValidationIssue(
                    "dangling-axiom-operation",
                    f"{axiom.name}: {', '.join(missing)}",
                )
            )
        if axiom.expression.count("(") != axiom.expression.count(")"):
            issues.append(ValidationIssue("unbalanced-axiom", axiom.name))
        for reference in axiom.referenced_operations:
            if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(reference)}(?![A-Za-z0-9_])", axiom.expression):
                issues.append(ValidationIssue("unmentioned-axiom-operation", f"{axiom.name}: {reference}"))

    operation_keys = {item.semantic_key for item in specification.operations}
    predicate_keys = {item.semantic_key for item in specification.predicates}
    for key in sorted(operation_keys.intersection(predicate_keys)):
        issues.append(
            ValidationIssue(
                "operation-predicate-overlap",
                key,
            )
        )
    for predicate in specification.predicates:
        if predicate.semantic_key.startswith(
            ("capability:", "transformation:", "observer:", "constant:")
        ):
            issues.append(
                ValidationIssue(
                    "capability-in-predicates",
                    predicate.semantic_key,
                )
            )

    counts = Counter(item.name for item in specification.operations)
    for name, count in counts.items():
        if count > 1:
            issues.append(ValidationIssue("duplicate-operation", name))

    allowed = {
        family.name
        for family in ontology.allowed_for(specification.perspective)
    }
    for family in specification.schema_families:
        if family not in allowed:
            issues.append(
                ValidationIssue(
                    "perspective-schema-mismatch",
                    f"{family} is not allowed for {specification.perspective}",
                )
            )
        for dependency in ontology.get(family).required_families:
            if dependency not in specification.schema_families:
                issues.append(
                    ValidationIssue(
                        "missing-schema-dependency",
                        f"{family} requires {dependency}",
                    )
                )

    for collection_name, collection in (
        ("sort", specification.sorts),
        ("operation", specification.operations),
        ("predicate", specification.predicates),
        ("axiom", specification.axioms),
    ):
        for item in collection:
            if not 0.0 <= item.confidence <= 1.0:
                issues.append(
                    ValidationIssue(
                        "invalid-confidence",
                        f"{collection_name} {item.name}: {item.confidence}",
                    )
                )

    if not specification.sorts:
        issues.append(ValidationIssue("empty-section", "sorts"))
    if not specification.operations:
        issues.append(ValidationIssue("empty-section", "operations"))
    return issues
