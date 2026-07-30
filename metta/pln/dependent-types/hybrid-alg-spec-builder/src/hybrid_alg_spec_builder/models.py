"""Typed domain model shared by all hybrid builder components."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ProvenanceKind(str, Enum):
    DIRECT_EVIDENCE = "direct-evidence"
    SCHEMA_IMPLIED = "schema-implied"
    ANALOGICAL = "analogically-inferred"
    LLM_PROPOSED = "llm-proposed"
    VALIDATED = "validated"
    HUMAN_APPROVED = "human-approved"


PROVENANCE_CONFIDENCE_CEILINGS = {
    ProvenanceKind.DIRECT_EVIDENCE: 0.92,
    ProvenanceKind.SCHEMA_IMPLIED: 0.84,
    ProvenanceKind.ANALOGICAL: 0.68,
    ProvenanceKind.LLM_PROPOSED: 0.55,
    ProvenanceKind.VALIDATED: 0.88,
    ProvenanceKind.HUMAN_APPROVED: 0.98,
}


@dataclass(frozen=True)
class Provenance:
    kind: ProvenanceKind
    source: str
    support: tuple[str, ...] = ()
    confidence: float = 0.5

    def clamped_confidence(self) -> float:
        ceiling = PROVENANCE_CONFIDENCE_CEILINGS[self.kind]
        return min(max(self.confidence, 0.0), ceiling)


@dataclass(frozen=True)
class EvidenceFact:
    relation: str
    source: str
    target: str
    weight: float = 1.0
    surface_text: str = ""
    source_file: str = ""
    order: int = 0

    @property
    def evidence_id(self) -> str:
        raw = f"{self.relation}|{self.source}|{self.target}|{self.source_file}|{self.order}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class CapabilityFrame:
    action: str
    family: str
    participant_roles: tuple[str, ...]
    input_sort: str
    output_sort: str
    provenance: list[Provenance] = field(default_factory=list)


@dataclass
class RelationFrame:
    predicate: str
    subject_sort: str
    object_sort: str
    object_value: str | None = None
    provenance: list[Provenance] = field(default_factory=list)


@dataclass(frozen=True)
class FormalOperation:
    name: str
    inputs: tuple[str, ...]
    output: str
    role: str
    semantic_key: str
    support: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True)
class FormalPredicate:
    name: str
    arguments: tuple[str, ...]
    semantic_key: str
    support: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True)
class FormalAxiom:
    name: str
    expression: str
    referenced_operations: tuple[str, ...]
    support: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass
class SemanticProposal:
    concept_kind: str = "unknown"
    sense: str = ""
    schema_families: list[str] = field(default_factory=list)
    sorts: list[str] = field(default_factory=list)
    operations: list[FormalOperation] = field(default_factory=list)
    predicates: list[FormalPredicate] = field(default_factory=list)
    axioms: list[FormalAxiom] = field(default_factory=list)
    capabilities: list[CapabilityFrame] = field(default_factory=list)
    relations: list[RelationFrame] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ConceptModel:
    concept: str
    perspective: str
    evidence: list[EvidenceFact] = field(default_factory=list)
    schema_families: list[str] = field(default_factory=list)
    capabilities: list[CapabilityFrame] = field(default_factory=list)
    relations: list[RelationFrame] = field(default_factory=list)
    retrieval_scores: dict[str, float] = field(default_factory=dict)
    concept_kind: str = "unknown"
    sense: str = ""
    formal_sorts: list[str] = field(default_factory=list)
    formal_operations: list[FormalOperation] = field(default_factory=list)
    formal_predicates: list[FormalPredicate] = field(default_factory=list)
    formal_axioms: list[FormalAxiom] = field(default_factory=list)

    def evidence_digest(self) -> str:
        payload = [
            ("context", self.sense),
            *[
            (
                fact.relation,
                fact.source,
                fact.target,
                fact.weight,
                fact.surface_text,
            )
            for fact in sorted(
                self.evidence,
                key=lambda item: (
                    item.relation,
                    item.source,
                    item.target,
                    item.order,
                ),
            )],
        ]
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()


@dataclass(frozen=True)
class SortDecl:
    name: str
    provenance: tuple[Provenance, ...]
    confidence: float


@dataclass(frozen=True)
class OperationDecl:
    name: str
    inputs: tuple[str, ...]
    output: str
    role: str
    semantic_key: str
    provenance: tuple[Provenance, ...]
    confidence: float


@dataclass(frozen=True)
class PredicateDecl:
    name: str
    arguments: tuple[str, ...]
    semantic_key: str
    provenance: tuple[Provenance, ...]
    confidence: float


@dataclass(frozen=True)
class AxiomDecl:
    name: str
    expression: str
    referenced_operations: tuple[str, ...]
    provenance: tuple[Provenance, ...]
    confidence: float


@dataclass
class AlgebraicSpecification:
    concept: str
    perspective: str
    sorts: list[SortDecl] = field(default_factory=list)
    operations: list[OperationDecl] = field(default_factory=list)
    predicates: list[PredicateDecl] = field(default_factory=list)
    axioms: list[AxiomDecl] = field(default_factory=list)
    schema_families: list[str] = field(default_factory=list)
    ontology_version: str = "1"
    evidence_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        def encode(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if hasattr(value, "__dataclass_fields__"):
                return {
                    key: encode(item)
                    for key, item in asdict(value).items()
                }
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [encode(item) for item in value]
            return value

        return encode(self)

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    detail: str
    severity: str = "error"


@dataclass
class BuildResult:
    specification: AlgebraicSpecification
    issues: list[ValidationIssue] = field(default_factory=list)
    cache_hit: bool = False
    used_llm: bool = False
    retrieved_schemas: list[tuple[str, float]] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)
