#!/usr/bin/env python3
"""Build a perspective-tagged algebraic-specification KB from ConceptNet atoms.

The input files in GeneralizationKB/concept-atomspace are six-line blocks:

    (relation source target)
    (source ...)
    (surfaceText ...)
    (weight ...)
    (relation ...)
    (target ...)

This script keeps that file-driven shape, but normalizes selected relations into
the fact schema consumed by the algebraic specification synthesizer:

    has-sort
    has-operation
    operation-signature
    has-predicate
    has-axiom

Each generated feature is tagged with a classified perspective, so the builder
can fetch only the spec features relevant to the requested context.
"""

import argparse
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


RELATION_PERSPECTIVES = {
    "isA": ("taxonomic-classification", "ontological-role"),
    "hasProperty": ("descriptive-property", "property-role"),
    "hasPrerequisite": ("prerequisite-action", "precondition-role"),
    "hasSubevent": ("event-composition", "process-role"),
}


@dataclass(frozen=True)
class Record:
    relation: str
    source: str
    target: str
    weight: float


def tokenize_relation(line):
    """Return tokens from a one-line MeTTa relation atom.

    This handles quoted atoms such as 'go_get_driver\\'s_license_renewed' and
    parenthesized target expressions conservatively, while preserving the token
    text so it can be emitted back into MeTTa.
    """

    text = line.strip()
    if not (text.startswith("(") and text.endswith(")")):
        return None

    text = text[1:-1].strip()
    tokens = []
    i = 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break

        if text[i] == "'":
            start = i
            i += 1
            escaped = False
            while i < len(text):
                ch = text[i]
                if ch == "'" and not escaped:
                    i += 1
                    break
                escaped = ch == "\\" and not escaped
                if ch != "\\":
                    escaped = False
                i += 1
            tokens.append(text[start:i])
            continue

        if text[i] == "(":
            start = i
            depth = 0
            while i < len(text):
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            tokens.append(text[start:i])
            continue

        start = i
        while i < len(text) and not text[i].isspace():
            i += 1
        tokens.append(text[start:i])

    return tokens


def parse_weight(line):
    match = re.search(r"\)\s+([-+]?\d+(?:\.\d+)?)\)$", line.strip())
    return float(match.group(1)) if match else 1.0


def iter_records(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    for index in range(0, len(lines), 6):
        if index >= len(lines):
            break

        tokens = tokenize_relation(lines[index])
        if not tokens or len(tokens) < 3:
            continue

        relation, source, target = tokens[0], tokens[1], tokens[2]
        if relation not in RELATION_PERSPECTIVES:
            continue

        weight = 1.0
        if index + 3 < len(lines) and lines[index + 3].startswith("(weight "):
            weight = parse_weight(lines[index + 3])

        yield Record(relation, source, target, weight)


def stv_from_weight(weight):
    evidence = max(weight, 0.1)
    score = math.log1p(evidence)
    strength = min(0.98, max(0.55, 0.55 + (score / 7.0)))
    confidence = min(0.94, max(0.4, 0.4 + (score / 9.0)))
    return f"(stv {strength:.3f} {confidence:.3f})"


def atom_id(*parts):
    raw = "-".join(str(part).strip("'") for part in parts)
    normalized = re.sub(r"[^A-Za-z0-9_+-]+", "-", raw)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or "feature"


def fact(proof, statement, tv):
    return f"(: {proof} (≞ {statement} {tv}))"


class FactWriter:
    def __init__(self):
        self.lines = []
        self.seen = set()

    def add(self, key, proof, statement, tv):
        if key in self.seen:
            return
        self.seen.add(key)
        self.lines.append(fact(proof, statement, tv))


def add_generic_sort(writer, concept, perspective, sort_name, tv):
    proof = atom_id("alg", "sort", concept, perspective, sort_name)
    edge = proof
    writer.add(
        ("sort", concept, perspective, sort_name),
        proof,
        f"(has-sort {edge} {concept} {perspective} {sort_name})",
        tv,
    )


def add_is_a(writer, record):
    perspective, _ = RELATION_PERSPECTIVES[record.relation]
    source, target, tv = record.source, record.target, stv_from_weight(record.weight)
    stem = atom_id("alg", "isa", source, target)

    writer.add(
        ("sort", source, perspective, target),
        f"{stem}-sort",
        f"(has-sort {stem}-sort {source} {perspective} {target})",
        tv,
    )
    writer.add(
        ("predicate", source, perspective, "isA", target),
        f"{stem}-predicate",
        f"(has-predicate {stem}-predicate {source} {perspective} (isA {source} {target}))",
        tv,
    )
    writer.add(
        ("axiom", source, perspective, "subsort", target),
        f"{stem}-axiom",
        f"(has-axiom {stem}-axiom {source} {perspective} (=> (isA {source} {target}) (subsort {source} {target})))",
        tv,
    )


def add_has_property(writer, record):
    perspective, _ = RELATION_PERSPECTIVES[record.relation]
    source, target, tv = record.source, record.target, stv_from_weight(record.weight)
    stem = atom_id("alg", "property", source, target)

    add_generic_sort(writer, source, perspective, "Property", "(stv 0.760 0.720)")
    writer.add(
        ("predicate", source, perspective, "hasProperty", target),
        f"{stem}-predicate",
        f"(has-predicate {stem}-predicate {source} {perspective} (hasProperty {source} {target}))",
        tv,
    )
    writer.add(
        ("axiom", source, perspective, "propertyOf", target),
        f"{stem}-axiom",
        f"(has-axiom {stem}-axiom {source} {perspective} (=> (hasProperty {source} {target}) (propertyOf {target} {source})))",
        tv,
    )


def add_has_prerequisite(writer, record):
    perspective, _ = RELATION_PERSPECTIVES[record.relation]
    source, target, tv = record.source, record.target, stv_from_weight(record.weight)
    stem = atom_id("alg", "prerequisite", source, target)

    add_generic_sort(writer, source, perspective, "ActionState", "(stv 0.780 0.730)")
    add_generic_sort(writer, source, perspective, "PreconditionState", "(stv 0.760 0.710)")
    writer.add(
        ("operation", source, perspective, target),
        f"{stem}-operation",
        f"(has-operation {stem}-operation {source} {perspective} {target})",
        tv,
    )
    writer.add(
        ("operation-signature", f"{stem}-operation"),
        f"{stem}-signature",
        f"(operation-signature {stem}-operation (-> PreconditionState ActionState ActionState))",
        "(stv 0.880 0.820)",
    )
    writer.add(
        ("predicate", source, perspective, "requires", target),
        f"{stem}-predicate",
        f"(has-predicate {stem}-predicate {source} {perspective} (requires {source} {target}))",
        tv,
    )
    writer.add(
        ("axiom", source, perspective, "requires", target),
        f"{stem}-axiom",
        f"(has-axiom {stem}-axiom {source} {perspective} (=> (perform {source}) (requires {source} {target})))",
        tv,
    )


def add_has_subevent(writer, record):
    perspective, _ = RELATION_PERSPECTIVES[record.relation]
    source, target, tv = record.source, record.target, stv_from_weight(record.weight)
    stem = atom_id("alg", "subevent", source, target)

    add_generic_sort(writer, source, perspective, "EventState", "(stv 0.780 0.730)")
    add_generic_sort(writer, source, perspective, "SubEventState", "(stv 0.760 0.710)")
    writer.add(
        ("operation", source, perspective, target),
        f"{stem}-operation",
        f"(has-operation {stem}-operation {source} {perspective} {target})",
        tv,
    )
    writer.add(
        ("operation-signature", f"{stem}-operation"),
        f"{stem}-signature",
        f"(operation-signature {stem}-operation (-> EventState SubEventState EventState))",
        "(stv 0.880 0.820)",
    )
    writer.add(
        ("predicate", source, perspective, "hasSubevent", target),
        f"{stem}-predicate",
        f"(has-predicate {stem}-predicate {source} {perspective} (hasSubevent {source} {target}))",
        tv,
    )
    writer.add(
        ("axiom", source, perspective, "performSubevent", target),
        f"{stem}-axiom",
        f"(has-axiom {stem}-axiom {source} {perspective} (=> (perform {source}) (perform {target})))",
        tv,
    )


ADDERS = {
    "isA": add_is_a,
    "hasProperty": add_has_property,
    "hasPrerequisite": add_has_prerequisite,
    "hasSubevent": add_has_subevent,
}


def build_facts(records, concepts, max_per_concept_relation):
    writer = FactWriter()
    counts = defaultdict(int)

    for perspective, perspective_class in sorted(set(RELATION_PERSPECTIVES.values())):
        proof = atom_id(perspective, "perspective")
        writer.add(
            ("perspective", perspective),
            proof,
            f"(classified-perspective {perspective} {perspective_class})",
            "(stv 1.000 1.000)",
        )

    for record in records:
        if concepts and record.source not in concepts:
            continue

        counter_key = (record.source, record.relation)
        if max_per_concept_relation is not None:
            if counts[counter_key] >= max_per_concept_relation:
                continue
            counts[counter_key] += 1

        ADDERS[record.relation](writer, record)

    return writer.lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Raw ConceptNet-style MeTTa relation file")
    parser.add_argument("output", help="Output normalized algebraic spec KB")
    parser.add_argument(
        "--concept",
        action="append",
        default=[],
        help="Only emit facts whose source concept matches this atom. Repeatable.",
    )
    parser.add_argument(
        "--max-per-concept-relation",
        type=int,
        default=None,
        help="Maximum raw edges to emit for each source concept and relation.",
    )
    args = parser.parse_args()

    records = iter_records(args.input)
    lines = build_facts(
        records,
        concepts=set(args.concept),
        max_per_concept_relation=args.max_per_concept_relation,
    )

    header = [
        ";; Generated by scripts/gen_algebraic_spec_kb.py.",
        ";; Perspective-tagged algebraic specification feature facts.",
        "",
    ]
    Path(args.output).write_text("\n".join(header + lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} facts to {args.output}")


if __name__ == "__main__":
    main()
