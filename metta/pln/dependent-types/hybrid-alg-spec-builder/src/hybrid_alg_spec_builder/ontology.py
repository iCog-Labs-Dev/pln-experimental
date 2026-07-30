"""Finite ontology of reusable algebraic schema families."""

from __future__ import annotations

from dataclasses import dataclass


ONTOLOGY_VERSION = "2026-07-24.2"


@dataclass(frozen=True)
class SchemaFamily:
    name: str
    perspectives: tuple[str, ...]
    keywords: tuple[str, ...]
    description: str
    required_families: tuple[str, ...] = ()

    @property
    def retrieval_document(self) -> str:
        return " ".join(
            (
                self.name,
                *self.perspectives,
                *self.keywords,
                self.description,
            )
        )


DEFAULT_SCHEMA_FAMILIES = (
    SchemaFamily("mathematical-structure", ("functional_use", "quantitative_comparative", "structural_composition"), ("mathematics", "number", "function", "operator", "proof", "law"), "Abstract carriers, typed operators, identities, and equational laws."),
    SchemaFamily("analysis-and-limits", ("functional_use", "quantitative_comparative"), ("limit", "convergence", "epsilon", "delta", "sequence", "topology", "continuity"), "Limits, approach, neighborhoods, convergence, and analytic laws.", ("mathematical-structure",)),
    SchemaFamily("spatial-container", ("functional_use", "spatial_context", "structural_composition"), ("building", "house", "room", "shelter", "occupy", "interior", "boundary"), "Habitable or spatial enclosures with occupants, regions, access, and containment."),
    SchemaFamily("information-transformation", ("functional_use", "information_computational"), ("information", "encode", "decode", "represent", "query", "document"), "Typed transformations and observations of information objects."),
    SchemaFamily("measurement-system", ("functional_use", "quantitative_comparative", "physical_attribute"), ("measure", "quantity", "unit", "scale", "error"), "Measurements, units, conversion, and uncertainty."),
    SchemaFamily("social-institution", ("functional_use", "social_normative"), ("institution", "organization", "role", "rule", "member", "authority"), "Roles, membership, authority, and institutional processes."),
    SchemaFamily("biological-process", ("functional_use", "behavioral_process", "state_lifecycle"), ("organism", "cell", "metabolism", "reproduce", "grow"), "Biological entities and state-changing life processes."),
    SchemaFamily(
        "functional-interface",
        ("functional_use",),
        ("use", "tool", "purpose", "instrument", "task", "apply"),
        "An artifact or resource configured and applied by an agent to a target.",
    ),
    SchemaFamily(
        "edge-application",
        ("functional_use",),
        ("knife", "blade", "cut", "slice", "pierce", "stab", "chop", "scrape"),
        "An edged instrument transforms a target through motion and force.",
        ("functional-interface",),
    ),
    SchemaFamily(
        "transport",
        ("functional_use", "spatial_context", "behavioral_process"),
        ("vehicle", "car", "carry", "drive", "travel", "transport", "route"),
        "Movement from an origin to a destination, possibly carrying cargo.",
    ),
    SchemaFamily(
        "containment",
        ("functional_use", "spatial_context", "structural_composition"),
        ("container", "box", "bottle", "bag", "hold", "store", "inside"),
        "Insertion, removal, and membership of objects in a container state.",
    ),
    SchemaFamily(
        "computation",
        ("information_computational", "functional_use"),
        ("computer", "program", "data", "calculate", "algorithm", "software"),
        "Initialization and transformation of computational state from input data.",
    ),
    SchemaFamily(
        "communication",
        ("behavioral_process", "information_computational", "social_normative"),
        ("communicate", "speak", "write", "message", "language", "conversation"),
        "Encoding, transmission, and receipt of messages between agents.",
    ),
    SchemaFamily(
        "perception",
        ("behavioral_process", "information_computational"),
        ("see", "hear", "sense", "observe", "eye", "ear", "perceive"),
        "Transformation of sensory input into an observation or experience.",
    ),
    SchemaFamily(
        "material-transformation",
        ("functional_use", "structural_composition"),
        ("material", "heat", "mix", "cook", "chemical", "transform"),
        "An action changes a material state into another material state.",
    ),
    SchemaFamily(
        "agent-action",
        ("behavioral_process",),
        ("agent", "person", "human", "act", "perform", "behavior"),
        "An agent performs actions that transition process state.",
    ),
    SchemaFamily(
        "structural-composition",
        ("structural_composition",),
        ("part", "whole", "component", "material", "assemble", "detach"),
        "Parts and materials compose a whole with an evolving structure state.",
    ),
    SchemaFamily(
        "taxonomic-interface",
        ("taxonomic_kind", "taxonomic_classification"),
        ("kind", "class", "type", "taxonomy", "instance", "classify"),
        "Classification and evidence-driven refinement of a concept kind.",
    ),
    SchemaFamily(
        "descriptive-observation",
        ("descriptive_property", "physical_attribute"),
        ("property", "attribute", "observe", "measure", "description"),
        "Observation of a property value in a context.",
    ),
    SchemaFamily(
        "risk-management",
        ("safety_risk",),
        ("risk", "hazard", "danger", "injury", "unsafe", "mitigate"),
        "Assessment and mitigation of risks in a hazard context.",
    ),
    SchemaFamily(
        "state-lifecycle",
        ("state_lifecycle", "temporal_context"),
        ("state", "event", "time", "transition", "old", "new", "lifecycle"),
        "Events transition a concept state over time.",
    ),
    SchemaFamily(
        "prerequisite-action",
        ("causal_prerequisite", "prerequisite_action"),
        ("requires", "precondition", "enable", "prerequisite", "before"),
        "A precondition enables an action that produces an outcome.",
    ),
    SchemaFamily(
        "spatial-state",
        ("spatial_context",),
        ("location", "path", "near", "inside", "at", "relocate"),
        "Observation and transformation of a concept location along a path.",
    ),
    SchemaFamily(
        "value-assessment",
        ("economic_ownership", "social_normative", "quantitative_comparative"),
        ("value", "price", "owner", "evaluation", "compare", "measure"),
        "Context-sensitive assessment or comparison producing a value.",
    ),
)


class OntologyRegistry:
    def __init__(self, families=DEFAULT_SCHEMA_FAMILIES):
        self._families = {family.name: family for family in families}

    @property
    def version(self) -> str:
        return ONTOLOGY_VERSION

    def get(self, name: str) -> SchemaFamily:
        return self._families[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._families))

    def families(self) -> tuple[SchemaFamily, ...]:
        return tuple(self._families[name] for name in sorted(self._families))

    def allowed_for(self, perspective: str) -> tuple[SchemaFamily, ...]:
        perspective = perspective.replace("-", "_")
        return tuple(
            family
            for family in self.families()
            if perspective in family.perspectives
        )

    def dependency_closure(self, names: list[str]) -> list[str]:
        result: list[str] = []

        def visit(name: str) -> None:
            if name in result or name not in self._families:
                return
            for dependency in self._families[name].required_families:
                visit(dependency)
            result.append(name)

        for name in names:
            visit(name)
        return result
