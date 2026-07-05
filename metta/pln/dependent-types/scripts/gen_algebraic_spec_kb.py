#!/usr/bin/env python3
"""Build a perspective-tagged algebraic-specification KB.

The source data is ConceptNet-style MeTTa with raw relation atoms such as:

    (isA apartment building)
    (hasproperty house susceptible_to_fire)
    (hasPrerequisite socialize go_to_party)
    (hasSubevent start_fire light_match)

Raw relations are treated as evidence, not as perspectives. Each relation is
first semantically classified into a formal perspective such as
taxonomic-kind, functional-use, physical-attribute, or safety-risk. Only then do
we emit algebraic-spec feature facts:

    has-sort
    has-operation
    operation-signature
    has-predicate
    has-axiom

Features are ranked and capped to the top N entries per concept, requested
perspective, and spec section. The default cap is 5.
"""

import argparse
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


RELATION_ALIASES = {
    "isA": "isA",
    "IsA": "isA",
    "hasproperty": "hasproperty",
    "Hasproperty": "hasproperty",
    "hasPrerequisite": "hasPrerequisite",
    "HasPrerequisite": "hasPrerequisite",
    "hasSubevent": "hasSubevent",
    "HasSubevent": "hasSubevent",
}
SUPPORTED_RELATIONS = set(RELATION_ALIASES.values())
SPEC_PARTS = ("sorts", "operations", "predicates", "axioms")


# A small formal ontology of reusable perspectives. The hierarchy is emitted as
# perspective-match facts, so the MeTTa builder can ask either for a narrow
# perspective (physical-attribute) or a broad one (descriptive-property).
PERSPECTIVES = {
    "descriptive-property": ("property-role", None),
    "taxonomic-classification": ("ontological-role", None),
    "prerequisite-action": ("precondition-role", None),
    "event-composition": ("process-role", None),
    "taxonomic-kind": ("kind-role", "taxonomic-classification"),
    "artifact-kind": ("artifact-kind-role", "taxonomic-kind"),
    "role-kind": ("role-kind-role", "taxonomic-kind"),
    "structural-composition": ("structure-role", None),
    "physical-attribute": ("physical-attribute-role", "descriptive-property"),
    "functional-use": ("function-role", "descriptive-property"),
    "behavioral-process": ("behavior-role", "event-composition"),
    "causal-prerequisite": ("causal-precondition-role", "prerequisite-action"),
    "spatial-context": ("spatial-role", "descriptive-property"),
    "temporal-context": ("temporal-role", "descriptive-property"),
    "quantitative-comparative": ("comparative-role", None),
    "social-normative": ("social-role", None),
    "economic-ownership": ("economic-role", "descriptive-property"),
    "information-computational": ("information-role", "descriptive-property"),
    "safety-risk": ("risk-role", "descriptive-property"),
    "state-lifecycle": ("state-role", "descriptive-property"),
}

PERSPECTIVE_SORTS = {
    "physical-attribute": ("concept_instance", "physical_attribute"),
    "functional-use": ("concept_instance", "function_role"),
    "behavioral-process": ("process_state", "behavior_state"),
    "causal-prerequisite": ("action_state", "precondition_state"),
    "spatial-context": ("concept_instance", "spatial_context"),
    "temporal-context": ("concept_instance", "temporal_context"),
    "quantitative-comparative": ("concept_instance", "comparative_measure"),
    "social-normative": ("concept_instance", "social_evaluation"),
    "economic-ownership": ("concept_instance", "economic_value"),
    "information-computational": ("concept_instance", "information_state"),
    "safety-risk": ("concept_instance", "risk_condition"),
    "state-lifecycle": ("concept_instance", "state_condition"),
    "structural-composition": ("whole", "part"),
}

HARD_REJECT_MARKERS = {
    "another_name_for",
    "another_word_for",
    "another_way_to_say",
    "both_",
    "one_kind_of",
    "one_type_of",
    "one_form_of",
    "one_individual_of",
    "popular_word",
    "singular_for",
    "sometimes_called",
    "word_people",
    "stolen_every",
}

MALFORMED_MARKERS = {
    "caculator",
    "toolds",
    "usfull",
    "inate",
    "alot",
    "fro_transportation",
}

ANECDOTAL_SURFACE_PREFIXES = (
    "my_",
    "this_",
    "that_",
    "your_",
    "his_",
    "her_",
)

VALUE_JUDGMENT_WORDS = {
    "annoying",
    "bad",
    "boring",
    "cruel",
    "dumb",
    "evil",
    "frightening",
    "fun",
    "guilty",
    "ignorant",
    "junk",
    "selfish",
    "stupid",
    "ugly",
    "weird",
    "wrong",
}

ECONOMIC_WORDS = {
    "bought",
    "buy",
    "cheap",
    "cost",
    "expensive",
    "market",
    "own",
    "ownership",
    "price",
    "sold",
}

SAFETY_WORDS = {
    "crash",
    "dangerous",
    "deadly",
    "fire",
    "hazard",
    "prone",
    "risk",
    "susceptible",
    "unsafe",
}

PHYSICAL_WORDS = {
    "black",
    "blue",
    "circular",
    "clear",
    "cold",
    "colorless",
    "odorless",
    "green",
    "hairy",
    "hard",
    "heavy",
    "hot",
    "invisible",
    "large",
    "liquid",
    "opaque",
    "orange",
    "red",
    "round",
    "shiny",
    "solid",
    "soft",
    "strong",
    "thinner",
    "transparent",
    "translucent",
    "white",
}

SPATIAL_WORDS = {
    "behind",
    "between",
    "driveway",
    "inside",
    "into",
    "left",
    "line",
    "near",
    "on",
    "outside",
    "place",
    "standing",
    "turning",
}

TEMPORAL_WORDS = {
    "annual",
    "daily",
    "frequent",
    "morning",
    "new",
    "old",
    "recent",
    "regular",
    "regularly",
    "sometimes",
    "times",
    "upgraded",
}

FUNCTIONAL_WORDS = {
    "able",
    "capable",
    "convenient",
    "easy",
    "function",
    "good_at",
    "hard_to_use",
    "help",
    "powered",
    "purpose",
    "reduce",
    "tool_to",
    "use",
    "used",
    "way_to",
}

INFORMATION_WORDS = {
    "arithmetic",
    "calculate",
    "computational",
    "data",
    "digital",
    "electronic",
    "hardware",
    "information",
    "mathematics",
    "numbers",
    "recording",
    "software",
}

PROCESS_WORDS = {
    "getting",
    "hurrying",
    "learning",
    "passing",
    "pushing",
    "reducing",
    "rolling",
    "standing",
    "turning",
}

STRUCTURAL_WORDS = {
    "component",
    "composed",
    "contains",
    "part",
    "portion",
    "structure",
    "within",
}

ARTIFACT_KIND_WORDS = {
    "appliance",
    "appliances",
    "artifact",
    "artifacts",
    "building",
    "buildings",
    "device",
    "devices",
    "equipment",
    "hardware",
    "instrument",
    "instruments",
    "machine",
    "machines",
    "structure",
    "structures",
    "system",
    "systems",
    "tool",
    "tools",
    "vehicle",
    "vehicles",
}

TAXONOMIC_KIND_WORDS = {
    "accommodation",
    "artifact",
    "building",
    "device",
    "electronic_device",
    "equipment",
    "event",
    "gas",
    "housing",
    "machine",
    "medium",
    "motor_vehicle",
    "place_to_live",
    "place_to_live_in",
    "process",
    "quality",
    "region",
    "structure",
    "tool",
    "vehicle",
    "wheeled_vehicle",
}


@dataclass(frozen=True)
class Record:
    relation: str
    source: str
    target: str
    weight: float
    surface_text: str
    source_file: str
    order: int


@dataclass(frozen=True)
class Classification:
    perspective: str
    target_type: str
    score_bonus: float = 0.0
    reject_reason: str | None = None


@dataclass(frozen=True)
class Candidate:
    group: tuple
    key: tuple
    score: float
    order: int
    lines: tuple


def tokenize_metta_atom(line):
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


def parse_float(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_metta_symbol(atom):
    text = atom[1:-1] if atom[:1] == chr(39) and atom[-1:] == chr(39) else atom
    text = text.strip("()")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_]", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text or not re.match(r"^[A-Za-z_]", text):
        text = f"c_{text}"
    return text


def iter_input_paths(inputs):
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            yield from sorted(path.rglob("*.metta"))
        elif path.exists():
            yield path


def iter_records_from_file(path):
    current = None
    order = 0

    def flush():
        if current is None:
            return None
        return Record(
            relation=current["relation"],
            source=safe_metta_symbol(current["source"]),
            target=safe_metta_symbol(current["target"]),
            weight=current["weight"],
            surface_text=current["surface_text"],
            source_file=str(path),
            order=current["order"],
        )

    with Path(path).open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            tokens = tokenize_metta_atom(line)
            if not tokens:
                continue

            head = tokens[0]
            canonical_relation = RELATION_ALIASES.get(head)
            if canonical_relation and len(tokens) >= 3:
                record = flush()
                if record:
                    yield record
                current = {
                    "relation": canonical_relation,
                    "source": tokens[1],
                    "target": tokens[2],
                    "weight": 1.0,
                    "surface_text": "",
                    "order": order,
                }
                order += 1
                continue

            if current is None:
                continue

            if head == "weight" and len(tokens) >= 3:
                current["weight"] = parse_float(tokens[-1], current["weight"])
            elif head == "surfaceText" and len(tokens) >= 3:
                current["surface_text"] = tokens[-1]

    record = flush()
    if record:
        yield record


def iter_records(inputs):
    for path in iter_input_paths(inputs):
        yield from iter_records_from_file(path)


def stv_from_weight(weight, confidence_floor=0.4):
    evidence = max(weight, 0.1)
    score = math.log1p(evidence)
    strength = min(0.98, max(0.55, 0.55 + (score / 7.0)))
    confidence = min(0.94, max(confidence_floor, confidence_floor + (score / 9.0)))
    return f"(stv {strength:.3f} {confidence:.3f})"


def strip_quotes(atom):
    return atom[1:-1] if atom.startswith("'") and atom.endswith("'") else atom


def plain_name(atom):
    text = strip_quotes(atom)
    text = text.strip("()")
    text = re.sub(r"\s+", "_", text)
    return text


def word_tokens(atom):
    text = plain_name(atom).lower()
    return tuple(token for token in re.split(r"[_\W]+", text) if token)


def joined(atom):
    return "_".join(word_tokens(atom))


def atom_id(*parts):
    raw = "-".join(plain_name(str(part)) for part in parts)
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", raw)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "feature"


def operation_name(prefix, target):
    name = atom_id(prefix, target).replace("-", "_")
    if not re.match(r"^[A-Za-z_]", name):
        name = f"{prefix}_{name}"
    return name


def static_safe_text(text):
    text = text.replace("->", "arrow")
    text = re.sub(r"(?<=[A-Za-z0-9_])[-+](?=[A-Za-z0-9_])", "_", text)
    text = re.sub(r"(?<![A-Za-z0-9_])[-+](?=[A-Za-z0-9_])", "_", text)
    return text


def fact(proof, statement, tv):
    return f"(: {static_safe_text(proof)} (≞ {static_safe_text(statement)} {tv}))"


def has_any_marker(text, markers):
    return any(marker in text for marker in markers)


def has_any_word(tokens, words):
    token_set = set(tokens)
    return bool(token_set.intersection(words))


def is_comparative_target(text, tokens):
    if "_than_" in text or "different_from" in text:
        return True
    comparative_words = {
        "better",
        "bigger",
        "cheaper",
        "faster",
        "heavier",
        "larger",
        "less",
        "lighter",
        "more",
        "slower",
        "smaller",
    }
    return has_any_word(tokens, comparative_words)


def surface_is_anecdotal(record):
    surface = joined(record.surface_text)
    return surface.startswith(ANECDOTAL_SURFACE_PREFIXES)


def reject_reason(record):
    target = joined(record.target)
    surface = joined(record.surface_text)

    if has_any_marker(target, HARD_REJECT_MARKERS):
        return "lexical-alias-or-metalinguistic-target"
    if has_any_marker(target, MALFORMED_MARKERS):
        return "malformed-target"
    if surface and surface_is_anecdotal(record):
        return "anecdotal-surface-text"
    return None


def classify_is_a(record):
    target = joined(record.target)
    tokens = word_tokens(record.target)

    if is_comparative_target(target, tokens):
        return Classification("quantitative-comparative", "comparative", -0.3)
    if has_any_word(tokens, VALUE_JUDGMENT_WORDS) or target.startswith("not_"):
        return Classification("social-normative", "evaluation", -0.2)
    if has_any_word(tokens, SPATIAL_WORDS) or target.startswith("in_"):
        return Classification("spatial-context", "spatial-context", -0.1)
    if has_any_word(tokens, TEMPORAL_WORDS):
        return Classification("temporal-context", "temporal-context", -0.1)
    if has_any_word(tokens, PROCESS_WORDS):
        return Classification("behavioral-process", "process", -0.1)
    if has_any_word(tokens, STRUCTURAL_WORDS):
        return Classification("structural-composition", "structural-relation", 0.08)
    if has_any_marker(target, FUNCTIONAL_WORDS) or has_any_word(tokens, FUNCTIONAL_WORDS):
        return Classification("functional-use", "function", 0.05)
    if has_any_word(tokens, ECONOMIC_WORDS):
        return Classification("economic-ownership", "economic-property", 0.08)
    if has_any_word(tokens, SAFETY_WORDS):
        return Classification("safety-risk", "risk-condition", 0.08)
    if target in TAXONOMIC_KIND_WORDS or has_any_word(tokens, ARTIFACT_KIND_WORDS):
        perspective = "artifact-kind" if has_any_word(tokens, ARTIFACT_KIND_WORDS) else "taxonomic-kind"
        return Classification(perspective, "kind", 0.35)
    if has_any_word(tokens, INFORMATION_WORDS):
        return Classification("information-computational", "information-kind", 0.18)
    if len(tokens) <= 3 and not has_any_word(tokens, PROCESS_WORDS | VALUE_JUDGMENT_WORDS):
        return Classification("taxonomic-kind", "kind", 0.05)

    return Classification("descriptive-property", "weak-description", -0.25)


def classify_has_property(record):
    target = joined(record.target)
    tokens = word_tokens(record.target)

    if is_comparative_target(target, tokens):
        return Classification("quantitative-comparative", "comparative", -0.25)
    if has_any_word(tokens, SAFETY_WORDS):
        return Classification("safety-risk", "risk-condition", 0.22)
    if has_any_marker(target, INFORMATION_WORDS) or has_any_word(tokens, INFORMATION_WORDS):
        return Classification("information-computational", "information-property", 0.25)
    if has_any_marker(target, FUNCTIONAL_WORDS) or has_any_word(tokens, FUNCTIONAL_WORDS):
        return Classification("functional-use", "capability", 0.2)
    if has_any_word(tokens, ECONOMIC_WORDS):
        return Classification("economic-ownership", "economic-property", 0.18)
    if has_any_word(tokens, PHYSICAL_WORDS):
        return Classification("physical-attribute", "physical-property", 0.18)
    if target in TAXONOMIC_KIND_WORDS or has_any_word(tokens, ARTIFACT_KIND_WORDS):
        return Classification(
            "taxonomic-kind",
            "kind-as-property",
            reject_reason="property-relation-targets-kind",
        )
    if has_any_word(tokens, TEMPORAL_WORDS):
        return Classification("state-lifecycle", "state-condition", 0.05)
    if has_any_word(tokens, SPATIAL_WORDS) or target.startswith("in_"):
        return Classification("spatial-context", "spatial-state", -0.05)
    if has_any_word(tokens, PROCESS_WORDS):
        return Classification("behavioral-process", "process-state", -0.05)
    if has_any_word(tokens, VALUE_JUDGMENT_WORDS):
        return Classification("social-normative", "evaluation", -0.2)
    if len(tokens) > 5:
        return Classification("descriptive-property", "weak-description", -0.15)

    return Classification("descriptive-property", "property", 0.0)


def classify_record(record, keep_noisy_targets=False):
    reason = reject_reason(record)
    if reason and not keep_noisy_targets:
        return Classification("descriptive-property", "rejected", reject_reason=reason)

    if record.relation == "isA":
        return classify_is_a(record)
    if record.relation == "hasproperty":
        return classify_has_property(record)
    if record.relation == "hasPrerequisite":
        return Classification("causal-prerequisite", "precondition", 0.2)
    if record.relation == "hasSubevent":
        return Classification("behavioral-process", "subevent", 0.2)

    return Classification("descriptive-property", "unknown", reject_reason="unsupported-relation")


def surface_quality(record):
    surface = joined(record.surface_text)
    quality = 0.0
    if not surface or surface == "na":
        return quality
    if "_is_a_" in surface or "_is_an_" in surface or "_is_type_of_" in surface:
        quality += 0.2
    if "_can_be_" in surface or surface.startswith("some_"):
        quality -= 0.12
    if "_generally_" in surface:
        quality += 0.06
    return quality


def target_quality(record, classification):
    target = joined(record.target)
    tokens = word_tokens(record.target)
    quality = classification.score_bonus

    if 1 <= len(tokens) <= 3:
        quality += 0.12
    elif len(tokens) >= 6:
        quality -= 0.2
    if target in TAXONOMIC_KIND_WORDS:
        quality += 0.25
    if classification.target_type in {"weak-description", "evaluation", "spatial-state"}:
        quality -= 0.18

    return quality


def base_score(record, classification):
    return math.log1p(max(record.weight, 0.1)) + target_quality(record, classification) + surface_quality(record)


def candidate(group, key, score, order, *lines):
    return Candidate(group=group, key=key, score=score, order=order, lines=tuple(lines))


def generic_sort_candidate(record, perspective, sort_name, classification, confidence=0.72, bonus=0.0):
    proof = atom_id("alg", "sort", record.source, perspective, sort_name)
    tv = f"(stv 0.760 {confidence:.3f})"
    return candidate(
        (record.source, perspective, "sorts"),
        ("sort", record.source, perspective, sort_name),
        base_score(record, classification) + bonus,
        record.order,
        fact(proof, f"(has-sort {proof} {record.source} {perspective} {sort_name})", tv),
    )


def predicate_for(record, classification):
    source, target = record.source, record.target
    if classification.perspective == "functional-use":
        return f"(hasFunction {source} {target})"
    if classification.perspective == "safety-risk":
        return f"(hasRisk {source} {target})"
    if classification.perspective == "economic-ownership":
        return f"(hasEconomicproperty {source} {target})"
    if classification.perspective == "information-computational":
        return f"(hasInformationproperty {source} {target})"
    if classification.perspective == "spatial-context":
        return f"(hasSpatialContext {source} {target})"
    if classification.perspective == "temporal-context":
        return f"(hasTemporalContext {source} {target})"
    if classification.perspective == "state-lifecycle":
        return f"(hasstate_condition {source} {target})"
    if classification.perspective == "quantitative-comparative":
        return f"(hasComparison {source} {target})"
    if classification.perspective == "social-normative":
        return f"(hasSocialEvaluation {source} {target})"
    if classification.perspective == "behavioral-process" and record.relation == "hasproperty":
        return f"(hasbehavior_state {source} {target})"
    if record.relation == "hasproperty":
        return f"(hasproperty {source} {target})"
    return f"({record.relation} {source} {target})"


def axiom_for(record, classification, predicate):
    source, target = record.source, record.target
    if classification.perspective == "functional-use":
        return f"(=> {predicate} (hasRole {target} {source}))"
    if classification.perspective == "safety-risk":
        return f"(=> {predicate} (riskOf {target} {source}))"
    if classification.perspective == "economic-ownership":
        return f"(=> {predicate} (economicFeatureOf {target} {source}))"
    if classification.perspective == "information-computational":
        return f"(=> {predicate} (informationFeatureOf {target} {source}))"
    if classification.perspective == "spatial-context":
        return f"(=> {predicate} (spatialContextOf {target} {source}))"
    if classification.perspective == "temporal-context":
        return f"(=> {predicate} (temporalContextOf {target} {source}))"
    if classification.perspective == "state-lifecycle":
        return f"(=> {predicate} (stateConditionOf {target} {source}))"
    if classification.perspective == "quantitative-comparative":
        return f"(=> {predicate} (comparisonOf {target} {source}))"
    if classification.perspective == "social-normative":
        return f"(=> {predicate} (socialEvaluationOf {target} {source}))"
    return f"(=> {predicate} (propertyOf {target} {source}))"


def operation_for_property(record, classification):
    target = joined(record.target)
    if classification.perspective == "physical-attribute":
        return operation_name("measure", target), "(-> concept_instance physical_attribute)"
    if classification.perspective == "functional-use":
        return operation_name("use_for", target), "(-> concept_instance functional_result)"
    if classification.perspective == "economic-ownership":
        return operation_name("assess", target), "(-> concept_instance economic_value)"
    if classification.perspective == "information-computational":
        if "arithmetic" in target:
            return "compute_arithmetic", "(-> concept_instance information_state)"
        if "numbers" in target:
            return "compute_numbers", "(-> concept_instance information_state)"
        return operation_name("process", target), "(-> concept_instance information_state)"
    if classification.perspective == "safety-risk":
        return operation_name("assess_risk", target), "(-> concept_instance risk_condition)"
    if classification.perspective == "state-lifecycle":
        return operation_name("observe_state", target), "(-> concept_instance state_condition)"
    if classification.perspective == "behavioral-process":
        return operation_name("perform", target), "(-> process_state process_state)"
    return None, None


def candidates_for_taxonomic(record, classification):
    perspective = classification.perspective
    source, target = record.source, record.target
    score = base_score(record, classification)
    tv = stv_from_weight(record.weight)
    stem = atom_id("alg", "isa", source, target)
    return [
        candidate(
            (source, perspective, "sorts"),
            ("sort", source, perspective, target),
            score + 0.35,
            record.order,
            fact(f"{stem}-sort", f"(has-sort {stem}-sort {source} {perspective} {target})", tv),
        ),
        candidate(
            (source, perspective, "predicates"),
            ("predicate", source, perspective, "isA", target),
            score,
            record.order,
            fact(f"{stem}-predicate", f"(has-predicate {stem}-predicate {source} {perspective} (isA {source} {target}))", tv),
        ),
        candidate(
            (source, perspective, "axioms"),
            ("axiom", source, perspective, "subsort", target),
            score,
            record.order,
            fact(
                f"{stem}-axiom",
                f"(has-axiom {stem}-axiom {source} {perspective} (=> (isA {source} {target}) (subsort {source} {target})))",
                tv,
            ),
        ),
    ]


def candidates_for_is_a(record, classification):
    if classification.perspective in {"taxonomic-kind", "artifact-kind", "role-kind"}:
        return candidates_for_taxonomic(record, classification)

    perspective = classification.perspective
    source, target = record.source, record.target
    score = base_score(record, classification)
    tv = stv_from_weight(record.weight)
    stem = atom_id("alg", "isa", source, target, perspective)
    predicate = predicate_for(record, classification)
    axiom = axiom_for(record, classification, predicate)
    items = []

    for sort_name in PERSPECTIVE_SORTS.get(perspective, ("concept_instance", "context_feature")):
        items.append(generic_sort_candidate(record, perspective, sort_name, classification))

    items.extend(
        [
            candidate(
                (source, perspective, "predicates"),
                ("predicate", source, perspective, predicate),
                score,
                record.order,
                fact(f"{stem}-predicate", f"(has-predicate {stem}-predicate {source} {perspective} {predicate})", tv),
            ),
            candidate(
                (source, perspective, "axioms"),
                ("axiom", source, perspective, axiom),
                score,
                record.order,
                fact(f"{stem}-axiom", f"(has-axiom {stem}-axiom {source} {perspective} {axiom})", tv),
            ),
        ]
    )
    return items


def candidates_for_has_property(record, classification):
    perspective = classification.perspective
    source, target = record.source, record.target
    score = base_score(record, classification)
    tv = stv_from_weight(record.weight)
    stem = atom_id("alg", "property", source, target, perspective)
    predicate = predicate_for(record, classification)
    axiom = axiom_for(record, classification, predicate)
    items = []

    for sort_name in PERSPECTIVE_SORTS.get(perspective, ("concept_instance", "property")):
        items.append(generic_sort_candidate(record, perspective, sort_name, classification))

    op, signature = operation_for_property(record, classification)
    if op and signature:
        items.append(
            candidate(
                (source, perspective, "operations"),
                ("operation", source, perspective, op),
                score - 0.03,
                record.order,
                fact(f"{stem}-operation", f"(has-operation {stem}-operation {source} {perspective} {op})", tv),
                fact(f"{stem}-signature", f"(operation-signature {stem}-operation {signature})", "(stv 0.820 0.740)"),
            )
        )

    items.extend(
        [
            candidate(
                (source, perspective, "predicates"),
                ("predicate", source, perspective, predicate),
                score,
                record.order,
                fact(f"{stem}-predicate", f"(has-predicate {stem}-predicate {source} {perspective} {predicate})", tv),
            ),
            candidate(
                (source, perspective, "axioms"),
                ("axiom", source, perspective, axiom),
                score,
                record.order,
                fact(f"{stem}-axiom", f"(has-axiom {stem}-axiom {source} {perspective} {axiom})", tv),
            ),
        ]
    )
    return items


def candidates_for_has_prerequisite(record, classification):
    perspective = classification.perspective
    source, target = record.source, record.target
    score = base_score(record, classification)
    tv = stv_from_weight(record.weight)
    stem = atom_id("alg", "prerequisite", source, target)
    operation_stem = atom_id("alg", "prerequisite", source, perspective)
    op = atom_id("establish_preconditions", source, perspective).replace("-", "_")

    return [
        generic_sort_candidate(record, perspective, "action_state", classification, bonus=0.1),
        generic_sort_candidate(record, perspective, "precondition_state", classification, bonus=0.1),
        candidate(
            (source, perspective, "operations"),
            ("operation", source, perspective, op),
            score,
            record.order,
            fact(f"{operation_stem}-operation", f"(has-operation {operation_stem}-operation {source} {perspective} {op})", tv),
            fact(
                f"{operation_stem}-signature",
                f"(operation-signature {operation_stem}-operation (-> precondition_state action_state action_state))",
                "(stv 0.880 0.820)",
            ),
        ),
        candidate(
            (source, perspective, "predicates"),
            ("predicate", source, perspective, "requires", target),
            score,
            record.order,
            fact(f"{stem}-predicate", f"(has-predicate {stem}-predicate {source} {perspective} (requires {source} {target}))", tv),
        ),
        candidate(
            (source, perspective, "axioms"),
            ("axiom", source, perspective, "requires", target),
            score,
            record.order,
            fact(
                f"{stem}-axiom",
                f"(has-axiom {stem}-axiom {source} {perspective} (=> (and (requires {source} {target}) (not (satisfied {target}))) (blocked {source})))",
                tv,
            ),
        ),
    ]


def candidates_for_has_subevent(record, classification):
    perspective = classification.perspective
    source, target = record.source, record.target
    score = base_score(record, classification)
    tv = stv_from_weight(record.weight)
    stem = atom_id("alg", "subevent", source, target)
    operation_stem = atom_id("alg", "subevent", source, perspective)
    op = atom_id("compose_process", source, perspective).replace("-", "_")

    return [
        generic_sort_candidate(record, perspective, "process_state", classification, bonus=0.1),
        generic_sort_candidate(record, perspective, "behavior_state", classification, bonus=0.1),
        candidate(
            (source, perspective, "operations"),
            ("operation", source, perspective, op),
            score,
            record.order,
            fact(f"{operation_stem}-operation", f"(has-operation {operation_stem}-operation {source} {perspective} {op})", tv),
            fact(
                f"{operation_stem}-signature",
                f"(operation-signature {operation_stem}-operation (-> process_state behavior_state process_state))",
                "(stv 0.880 0.820)",
            ),
        ),
        candidate(
            (source, perspective, "predicates"),
            ("predicate", source, perspective, "hasSubevent", target),
            score,
            record.order,
            fact(f"{stem}-predicate", f"(has-predicate {stem}-predicate {source} {perspective} (hasSubevent {source} {target}))", tv),
        ),
        candidate(
            (source, perspective, "axioms"),
            ("axiom", source, perspective, "performSubevent", target),
            score,
            record.order,
            fact(
                f"{stem}-axiom",
                f"(has-axiom {stem}-axiom {source} {perspective} (=> (and (hasSubevent {source} {target}) (not (completed {target}))) (incomplete {source})))",
                tv,
            ),
        ),
    ]


CANDIDATE_BUILDERS = {
    "isA": candidates_for_is_a,
    "hasproperty": candidates_for_has_property,
    "hasPrerequisite": candidates_for_has_prerequisite,
    "hasSubevent": candidates_for_has_subevent,
}


def select_candidates(records, concepts, max_per_part, max_per_concept_relation, keep_noisy_targets):
    best_by_key = {}
    relation_counts = defaultdict(int)
    seen_records = 0
    rejected = Counter()
    classified = Counter()

    for record in records:
        seen_records += 1
        if concepts and record.source not in concepts:
            continue

        classification = classify_record(record, keep_noisy_targets=keep_noisy_targets)
        if classification.reject_reason:
            rejected[classification.reject_reason] += 1
            continue
        classified[classification.perspective] += 1

        relation_key = (record.source, record.relation)
        if max_per_concept_relation is not None:
            if relation_counts[relation_key] >= max_per_concept_relation:
                continue
            relation_counts[relation_key] += 1

        for item in CANDIDATE_BUILDERS[record.relation](record, classification):
            previous = best_by_key.get(item.key)
            if previous is None or (item.score, -item.order) > (previous.score, -previous.order):
                best_by_key[item.key] = item

    grouped = defaultdict(list)
    for item in best_by_key.values():
        grouped[item.group].append(item)

    selected = []
    for group in sorted(grouped):
        ranked = sorted(grouped[group], key=lambda item: (-item.score, item.order, item.key))
        selected.extend(ranked[:max_per_part])

    return selected, seen_records, rejected, classified


def perspective_ancestors(perspective):
    current = perspective
    while current:
        yield current
        current = PERSPECTIVES[current][1]


def perspective_lines():
    lines = []

    for perspective, (perspective_class, parent) in sorted(PERSPECTIVES.items()):
        proof = atom_id(perspective, "perspective")
        lines.append(
            fact(
                proof,
                f"(classified-perspective {perspective} {perspective_class})",
                "(stv 1.000 1.000)",
            )
        )
        if parent:
            lines.append(
                fact(
                    atom_id(perspective, "subperspective", parent),
                    f"(subperspective {perspective} {parent})",
                    "(stv 1.000 1.000)",
                )
            )

    for actual, (perspective_class, _parent) in sorted(PERSPECTIVES.items()):
        for requested in perspective_ancestors(actual):
            tv = "(stv 1.000 1.000)" if requested == actual else "(stv 0.970 1.000)"
            lines.append(
                fact(
                    atom_id(requested, "matches", actual),
                    f"(perspective-match {requested} {actual} {perspective_class})",
                    tv,
                )
            )

    return lines


def build_output_lines(records, concepts, max_per_part, max_per_concept_relation, keep_noisy_targets):
    selected, seen_records, rejected, classified = select_candidates(
        records=records,
        concepts=concepts,
        max_per_part=max_per_part,
        max_per_concept_relation=max_per_concept_relation,
        keep_noisy_targets=keep_noisy_targets,
    )

    lines = perspective_lines()
    seen_lines = set(lines)
    for item in selected:
        for line in item.lines:
            if line in seen_lines:
                continue
            seen_lines.add(line)
            lines.append(line)

    return lines, selected, seen_records, rejected, classified


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", help="Raw MeTTa relation files or directories")
    parser.add_argument("output", help="Output normalized algebraic spec KB")
    parser.add_argument(
        "--concept",
        action="append",
        default=[],
        help="Only emit facts whose source concept matches this atom. Repeatable.",
    )
    parser.add_argument(
        "--top-concepts",
        type=int,
        default=None,
        help="Also emit facts for the N source concepts with the most raw relation records.",
    )
    parser.add_argument(
        "--max-per-part",
        type=int,
        default=5,
        help="Maximum selected sorts, operations, predicates, and axioms per concept/perspective.",
    )
    parser.add_argument(
        "--max-per-concept-relation",
        type=int,
        default=None,
        help="Optional prefilter limit for raw edges per source concept and relation.",
    )
    parser.add_argument(
        "--keep-noisy-targets",
        action="store_true",
        help="Keep alias-like, anecdotal, or malformed target facts instead of filtering them.",
    )
    args = parser.parse_args()

    concepts = set(args.concept)
    records = iter_records(args.inputs)
    if args.top_concepts is not None:
        records = list(records)
        top_sources = [
            source
            for source, _count in Counter(record.source for record in records).most_common(args.top_concepts)
        ]
        concepts.update(top_sources)

    lines, selected, seen_records, rejected, classified = build_output_lines(
        records=records,
        concepts=concepts,
        max_per_part=args.max_per_part,
        max_per_concept_relation=args.max_per_concept_relation,
        keep_noisy_targets=args.keep_noisy_targets,
    )

    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    grouped = defaultdict(int)
    for item in selected:
        grouped[item.group[2]] += 1

    print(f"Read {seen_records} raw relation records")
    print(f"Rejected {sum(rejected.values())} raw records")
    for reason, count in rejected.most_common(5):
        print(f"  rejected {reason}: {count}")
    print(f"Classified {sum(classified.values())} raw records")
    for perspective, count in classified.most_common(10):
        print(f"  perspective {perspective}: {count}")
    print(f"Selected {len(selected)} ranked feature candidates")
    for part in SPEC_PARTS:
        print(f"  {part}: {grouped[part]}")
    print(f"Wrote {len(lines)} facts to {args.output}")


if __name__ == "__main__":
    main()


# (Concept socialize (perspective prerequisite-action) 
# (spec (sorts ((: 
# (SpecSort alg-sort-socialize-causal-prerequisite-action_state prerequisite-action-matches-causal-prerequisite) (≞ (spec-sort socialize prerequisite-action causal-precondition-role action_state) (stv 0.7372 0.72))) (: 
# (SpecSort alg-sort-socialize-causal-prerequisite-precondition_state prerequisite-action-matches-causal-prerequisite) (≞ (spec-sort socialize prerequisite-action causal-precondition-role precondition_state) (stv 0.7372 0.72))))) 
# (ops (
# (: (SpecOperation alg-prerequisite-socialize-meet_people-operation alg-prerequisite-socialize-meet_people-signature prerequisite-action-matches-causal-prerequisite)
#  (≞ (spec-operation socialize prerequisite-action causal-precondition-role (operation prepare_meet_people (-> precondition_state action_state action_state))) (stv 0.6769048000000001 0.589))) 
# (: (SpecOperation alg-prerequisite-socialize-go_to_clubs-operation alg-prerequisite-socialize-go_to_clubs-signature prerequisite-action-matches-causal-prerequisite)
#  (≞ (spec-operation socialize prerequisite-action causal-precondition-role (operation prepare_go_to_clubs (-> precondition_state action_state action_state))) (stv 0.6034952 0.522))) 
# (: (SpecOperation alg-prerequisite-socialize-go_to_party-operation alg-prerequisite-socialize-go_to_party-signature prerequisite-action-matches-causal-prerequisite)
#  (≞ (spec-operation socialize prerequisite-action causal-precondition-role (operation prepare_go_to_party (-> precondition_state action_state action_state))) (stv 0.6034952 0.522))) 
# (: (SpecOperation alg-prerequisite-socialize-have_friends-operation alg-prerequisite-socialize-have_friends-signature prerequisite-action-matches-causal-prerequisite)
#  (≞ (spec-operation socialize prerequisite-action causal-precondition-role (operation prepare_have_friends (-> precondition_state action_state action_state))) (stv 0.6034952 0.522))) 
# (: (SpecOperation alg-prerequisite-socialize-talk_to_people-operation alg-prerequisite-socialize-talk_to_people-signature prerequisite-action-matches-causal-prerequisite)
#  (≞ (spec-operation socialize prerequisite-action causal-precondition-role (operation prepare_talk_to_people (-> precondition_state action_state action_state))) (stv 0.6034952 0.522))))) 
# (preds (
# (: (SpecPredicate alg-prerequisite-socialize-meet_people-predicate prerequisite-action-matches-causal-prerequisite) (≞ (spec-predicate socialize prerequisite-action causal-precondition-role (requires socialize meet_people)) (stv 0.7692100000000001 0.589))) 
# (: (SpecPredicate alg-prerequisite-socialize-go_to_clubs-predicate prerequisite-action-matches-causal-prerequisite) (≞ (spec-predicate socialize prerequisite-action causal-precondition-role (requires socialize go_to_clubs)) (stv 0.6857899999999999 0.522))) 
# (: (SpecPredicate alg-prerequisite-socialize-go_to_party-predicate prerequisite-action-matches-causal-prerequisite) (≞ (spec-predicate socialize prerequisite-action causal-precondition-role (requires socialize go_to_party)) (stv 0.6857899999999999 0.522))) 
# (: (SpecPredicate alg-prerequisite-socialize-have_friends-predicate prerequisite-action-matches-causal-prerequisite) (≞ (spec-predicate socialize prerequisite-action causal-precondition-role (requires socialize have_friends)) (stv 0.6857899999999999 0.522))) 
# (: (SpecPredicate alg-prerequisite-socialize-talk_to_people-predicate prerequisite-action-matches-causal-prerequisite) (≞ (spec-predicate socialize prerequisite-action causal-precondition-role (requires socialize talk_to_people)) (stv 0.6857899999999999 0.522))))) 
# (axioms (
# (: (SpecAxiom alg-prerequisite-socialize-meet_people-axiom prerequisite-action-matches-causal-prerequisite) (≞ (spec-axiom socialize prerequisite-action causal-precondition-role (=> (perform socialize) (requires socialize meet_people))) (stv 0.7692100000000001 0.589))) 
# (: (SpecAxiom alg-prerequisite-socialize-go_to_clubs-axiom prerequisite-action-matches-causal-prerequisite) (≞ (spec-axiom socialize prerequisite-action causal-precondition-role (=> (perform socialize) (requires socialize go_to_clubs))) (stv 0.6857899999999999 0.522))) 
# (: (SpecAxiom alg-prerequisite-socialize-go_to_party-axiom prerequisite-action-matches-causal-prerequisite) (≞ (spec-axiom socialize prerequisite-action causal-precondition-role (=> (perform socialize) (requires socialize go_to_party))) (stv 0.6857899999999999 0.522))) 
# (: (SpecAxiom alg-prerequisite-socialize-have_friends-axiom prerequisite-action-matches-causal-prerequisite) (≞ (spec-axiom socialize prerequisite-action causal-precondition-role (=> (perform socialize) (requires socialize have_friends))) (stv 0.6857899999999999 0.522))) 
# (: (SpecAxiom alg-prerequisite-socialize-talk_to_people-axiom prerequisite-action-matches-causal-prerequisite) (≞ (spec-axiom socialize prerequisite-action causal-precondition-role (=> (perform socialize) (requires socialize talk_to_people))) (stv 0.6857899999999999 0.522))))))
# )
