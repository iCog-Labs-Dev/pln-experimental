"""Evidence normalization and semantic-frame grounding."""

from __future__ import annotations

import re

from .embeddings import RetrievalHit
from .models import (
    CapabilityFrame,
    ConceptModel,
    EvidenceFact,
    Provenance,
    ProvenanceKind,
    RelationFrame,
    SemanticProposal,
)
from .ontology import OntologyRegistry


ACTION_ALIASES = {
    "cut": ("slice", "edge-application"),
    "cutting": ("slice", "edge-application"),
    "slice": ("slice", "edge-application"),
    "stab": ("pierce", "edge-application"),
    "stabbing": ("pierce", "edge-application"),
    "pierce": ("pierce", "edge-application"),
    "chop": ("chop", "edge-application"),
    "scrape": ("scrape", "edge-application"),
    "drive": ("transport", "transport"),
    "travel": ("transport", "transport"),
    "transport": ("transport", "transport"),
    "carry": ("carry", "transport"),
    "store": ("insert", "containment"),
    "hold": ("contain", "containment"),
    "contain": ("contain", "containment"),
    "calculate": ("compute", "computation"),
    "compute": ("compute", "computation"),
    "communicate": ("communicate", "communication"),
    "speak": ("communicate", "communication"),
    "write": ("communicate", "communication"),
    "see": ("perceive", "perception"),
    "hear": ("perceive", "perception"),
    "observe": ("perceive", "perception"),
    "heat": ("transform", "material-transformation"),
    "mix": ("transform", "material-transformation"),
    "cook": ("transform", "material-transformation"),
    "learn": ("learn", "agent-action"),
    "reason": ("reason", "agent-action"),
}

RELATION_MAP = {
    "isA": ("IsA", "taxonomic_kind"),
    "InstanceOf": ("InstanceOf", "taxonomic_kind"),
    "hasproperty": ("HasProperty", "property"),
    "hasPrerequisite": ("Requires", "precondition"),
    "hasSubevent": ("HasSubevent", "event"),
    "ReceivesAction": ("ReceivesAction", "action"),
    "Causes": ("MayCause", "risk"),
    "Entails": ("Entails", "outcome"),
    "CausesDesire": ("CausesDesire", "desire"),
    "HasA": ("HasPart", "part"),
    "PartOf": ("PartOf", "whole"),
    "MadeOf": ("MadeOf", "material"),
    "AtLocation": ("AtLocation", "location"),
    "LocatedNear": ("LocatedNear", "location"),
    "HasContext": ("HasContext", "context"),
    "CreatedBy": ("CreatedBy", "agent"),
    "RelatedTo": ("RelatedTo", "related_entity"),
}


def tokens(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in re.split(r"[_\W]+", value.lower())
        if token
    )


def _direct_provenance(fact: EvidenceFact) -> Provenance:
    confidence = min(0.92, 0.55 + 0.08 * max(fact.weight, 0.0))
    return Provenance(
        ProvenanceKind.DIRECT_EVIDENCE,
        fact.evidence_id,
        (f"{fact.relation}({fact.source},{fact.target})",),
        confidence,
    )


def _action_for(fact: EvidenceFact) -> tuple[str, str] | None:
    if fact.relation not in {"UsedFor", "CapableOf"}:
        return None
    for token in tokens(fact.target):
        if token in ACTION_ALIASES:
            return ACTION_ALIASES[token]
    if fact.relation == "CapableOf" and 1 <= len(tokens(fact.target)) <= 3:
        return "_".join(tokens(fact.target)), "agent-action"
    return None


def build_grounded_model(
    concept: str,
    perspective: str,
    evidence: list[EvidenceFact],
    retrieval_hits: list[RetrievalHit],
    ontology: OntologyRegistry,
) -> ConceptModel:
    perspective = perspective.replace("-", "_")
    model = ConceptModel(concept, perspective, evidence=list(evidence))
    schema_hits = [hit for hit in retrieval_hits if hit.kind == "schema"]
    evidence_tokens = set(tokens(concept))
    for fact in evidence:
        evidence_tokens.update(tokens(fact.source))
        evidence_tokens.update(tokens(fact.target))
        evidence_tokens.update(tokens(fact.surface_text))
    retrieved_names = [
        hit.name
        for hit in schema_hits
        if (
            evidence_tokens.intersection(ontology.get(hit.name).keywords)
            # A neural embedding provider may bridge a genuine lexical gap.
            # The deliberately conservative threshold prevents the offline
            # hash fallback from activating weakly related families.
            or hit.score >= 0.55
        )
    ][:1]
    model.retrieval_scores.update({hit.name: hit.score for hit in schema_hits})

    for fact in evidence:
        action = _action_for(fact) if fact.source == concept else None
        if action:
            action_name, family = action
            if perspective not in ontology.get(family).perspectives:
                continue
            model.capabilities.append(
                CapabilityFrame(
                    action_name,
                    family,
                    ("agent", "target"),
                    "input_state",
                    "output_state",
                    [_direct_provenance(fact)],
                )
            )
            retrieved_names.append(family)
            continue

        if fact.relation == "UsedFor" and fact.source == concept:
            model.relations.append(
                RelationFrame(
                    "ServesTask",
                    concept,
                    "task",
                    fact.target,
                    [_direct_provenance(fact)],
                )
            )
            continue

        relation = RELATION_MAP.get(fact.relation)
        if relation and fact.source == concept:
            predicate, object_sort = relation
            model.relations.append(
                RelationFrame(
                    predicate,
                    concept,
                    object_sort,
                    fact.target,
                    [_direct_provenance(fact)],
                )
            )

    allowed = {family.name for family in ontology.allowed_for(perspective)}
    base_by_perspective = {
        "functional_use": "functional-interface",
        "behavioral_process": "agent-action",
        "information_computational": "computation",
        "structural_composition": "structural-composition",
        "taxonomic_kind": "taxonomic-interface",
        "taxonomic_classification": "taxonomic-interface",
        "descriptive_property": "descriptive-observation",
        "physical_attribute": "descriptive-observation",
        "safety_risk": "risk-management",
        "state_lifecycle": "state-lifecycle",
        "temporal_context": "state-lifecycle",
        "causal_prerequisite": "prerequisite-action",
        "prerequisite_action": "prerequisite-action",
        "spatial_context": "spatial-state",
        "economic_ownership": "value-assessment",
        "social_normative": "value-assessment",
        "quantitative_comparative": "value-assessment",
    }
    base = base_by_perspective.get(perspective)
    # functional_use is a question, not a universal physical-tool signature.
    # Keep its generic fallback only when retrieval found no domain model.
    if base and not (perspective == "functional_use" and retrieved_names):
        retrieved_names.append(base)
    model.schema_families = ontology.dependency_closure(
        [name for name in retrieved_names if name in allowed]
    )
    return model


def merge_proposal(
    model: ConceptModel,
    proposal: SemanticProposal,
    ontology: OntologyRegistry,
) -> None:
    model.concept_kind = proposal.concept_kind
    model.sense = proposal.sense
    model.formal_sorts = list(dict.fromkeys(proposal.sorts))
    model.formal_operations = list(proposal.operations)
    model.formal_predicates = list(proposal.predicates)
    model.formal_axioms = list(proposal.axioms)
    allowed = {family.name for family in ontology.allowed_for(model.perspective)}
    proposed_families = [name for name in proposal.schema_families if name in allowed]
    model.schema_families = ontology.dependency_closure(
        proposed_families if proposal.operations else model.schema_families + proposed_families
    )
    existing_capabilities = {
        (frame.action, frame.family)
        for frame in model.capabilities
    }
    for frame in proposal.capabilities:
        if frame.family in allowed and (frame.action, frame.family) not in existing_capabilities:
            model.capabilities.append(frame)
    existing_relations = {
        (frame.predicate, frame.object_sort, frame.object_value)
        for frame in model.relations
    }
    for frame in proposal.relations:
        key = (frame.predicate, frame.object_sort, frame.object_value)
        if key not in existing_relations:
            model.relations.append(frame)
