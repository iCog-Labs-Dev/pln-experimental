"""Deterministic compilation of semantic models into algebraic specifications."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import (
    AlgebraicSpecification,
    AxiomDecl,
    ConceptModel,
    OperationDecl,
    PredicateDecl,
    Provenance,
    ProvenanceKind,
    SortDecl,
)
from .ontology import OntologyRegistry


def _confidence(provenance: Iterable[Provenance], default: float = 0.62) -> float:
    values = [item.clamped_confidence() for item in provenance]
    if not values:
        return default
    values.sort(reverse=True)
    strongest = values[0]
    corroboration = sum(values[1:]) / max(1, len(values) - 1)
    return min(0.98, strongest + (1.0 - strongest) * 0.15 * corroboration)


def _merge_provenance(*groups: Iterable[Provenance]) -> tuple[Provenance, ...]:
    unique = {}
    for group in groups:
        for item in group:
            key = (item.kind, item.source, item.support, item.confidence)
            unique[key] = item
    return tuple(unique.values())


class SpecificationAssembler:
    def __init__(self, model: ConceptModel, ontology: OntologyRegistry):
        self.model = model
        self.ontology = ontology
        self.spec = AlgebraicSpecification(
            concept=model.concept,
            perspective=model.perspective,
            schema_families=list(model.schema_families),
            ontology_version=ontology.version,
            evidence_digest=model.evidence_digest(),
        )
        self._sorts: dict[str, SortDecl] = {}
        self._operations: dict[str, OperationDecl] = {}
        self._predicates: dict[tuple[str, tuple[str, ...]], PredicateDecl] = {}
        self._axioms: dict[str, AxiomDecl] = {}

    def schema_provenance(self, family: str) -> tuple[Provenance, ...]:
        score = self.model.retrieval_scores.get(family)
        result = [
            Provenance(
                ProvenanceKind.SCHEMA_IMPLIED,
                f"ontology:{family}:{self.ontology.version}",
                (family,),
                0.80,
            )
        ]
        if score is not None:
            result.append(
                Provenance(
                    ProvenanceKind.ANALOGICAL,
                    f"embedding:{family}",
                    (f"retrieval-score={score:.4f}",),
                    min(0.68, max(0.25, 0.45 + score * 0.25)),
                )
            )
        return tuple(result)

    def add_sort(self, name: str, provenance: tuple[Provenance, ...]) -> None:
        current = self._sorts.get(name)
        combined = _merge_provenance(
            provenance,
            current.provenance if current else (),
        )
        self._sorts[name] = SortDecl(name, combined, _confidence(combined))

    def add_operation(
        self,
        name: str,
        inputs: tuple[str, ...],
        output: str,
        role: str,
        semantic_key: str,
        provenance: tuple[Provenance, ...],
    ) -> None:
        for sort in (*inputs, output):
            self.add_sort(sort, provenance)
        self._operations[name] = OperationDecl(
            name,
            inputs,
            output,
            role,
            semantic_key,
            provenance,
            _confidence(provenance),
        )

    def add_predicate(
        self,
        name: str,
        arguments: tuple[str, ...],
        semantic_key: str,
        provenance: tuple[Provenance, ...],
    ) -> None:
        for sort in arguments:
            self.add_sort(sort, provenance)
        key = (name, arguments)
        current = self._predicates.get(key)
        combined = _merge_provenance(
            provenance,
            current.provenance if current else (),
        )
        self._predicates[key] = PredicateDecl(
            name,
            arguments,
            semantic_key,
            combined,
            _confidence(combined),
        )

    def add_axiom(
        self,
        name: str,
        expression: str,
        operations: tuple[str, ...],
        provenance: tuple[Provenance, ...],
    ) -> None:
        self._axioms[name] = AxiomDecl(
            name,
            expression,
            operations,
            provenance,
            _confidence(provenance),
        )

    def finish(self) -> AlgebraicSpecification:
        self.spec.sorts = sorted(self._sorts.values(), key=lambda item: item.name)
        self.spec.operations = sorted(
            self._operations.values(),
            key=lambda item: (item.role, item.name),
        )
        self.spec.predicates = sorted(
            self._predicates.values(),
            key=lambda item: (item.name, item.arguments),
        )
        self.spec.axioms = sorted(self._axioms.values(), key=lambda item: item.name)
        return self.spec


def _functional(asm: SpecificationAssembler) -> None:
    c = asm.model.concept
    p = asm.schema_provenance("functional-interface")
    for sort in (
        c,
        "agent",
        "target",
        "use_path",
        "motion",
        "force",
        "use_configuration",
        "use_outcome",
        "task",
        "risk",
    ):
        asm.add_sort(sort, p)
    operations = (
        (f"configure_{c}", ("agent", c, "target", "use_path"), "use_configuration", "constructor", "capability:configure"),
        (f"target_of_{c}", ("use_configuration",), "target", "observer", "observer:target"),
        (f"retarget_{c}", ("use_configuration", "target"), "use_configuration", "transformation", "transformation:retarget"),
        (f"apply_{c}", ("use_configuration", "motion", "force"), "use_outcome", "transformation", "capability:apply"),
        (f"target_after_{c}", ("use_outcome",), "target", "observer", "observer:target_after"),
        (f"no_motion_{c}", (), "motion", "constant", "constant:no_motion"),
        (f"zero_force_{c}", (), "force", "constant", "constant:zero_force"),
        (f"compose_motion_{c}", ("motion", "motion"), "motion", "combinator", "combinator:motion"),
    )
    for operation in operations:
        asm.add_operation(*operation, p)
    for name, arguments in (
        ("UsedBy", (c, "agent")),
        ("AppliedTo", (c, "target")),
        ("GuidedAlong", (c, "use_path")),
        ("ServesTask", (c, "task")),
        ("Produces", (c, "use_outcome")),
        ("MayCause", (c, "risk")),
        ("RequiresForce", (c, "force")),
        ("ControlledBy", (c, "agent")),
    ):
        asm.add_predicate(name, arguments, f"relation:{name}", p)
    axioms = (
        (
            "configure_target",
            f"(forall ((a agent) (k {c}) (t target) (p use_path)) (= (target_of_{c} (configure_{c} a k t p)) t))",
            (f"target_of_{c}", f"configure_{c}"),
        ),
        (
            "retarget_target",
            f"(forall ((cfg use_configuration) (t target)) (= (target_of_{c} (retarget_{c} cfg t)) t))",
            (f"target_of_{c}", f"retarget_{c}"),
        ),
        (
            "no_motion_identity",
            f"(forall ((cfg use_configuration) (f force)) (= (target_after_{c} (apply_{c} cfg no_motion_{c} f)) (target_of_{c} cfg)))",
            (f"target_after_{c}", f"apply_{c}", f"no_motion_{c}", f"target_of_{c}"),
        ),
        (
            "zero_force_identity",
            f"(forall ((cfg use_configuration) (m motion)) (= (target_after_{c} (apply_{c} cfg m zero_force_{c})) (target_of_{c} cfg)))",
            (f"target_after_{c}", f"apply_{c}", f"zero_force_{c}", f"target_of_{c}"),
        ),
        (
            "motion_left_identity",
            f"(forall ((m motion)) (= (compose_motion_{c} no_motion_{c} m) m))",
            (f"compose_motion_{c}", f"no_motion_{c}"),
        ),
        (
            "motion_right_identity",
            f"(forall ((m motion)) (= (compose_motion_{c} m no_motion_{c}) m))",
            (f"compose_motion_{c}", f"no_motion_{c}"),
        ),
    )
    for name, expression, refs in axioms:
        asm.add_axiom(name, expression, refs, p)


def _edge_application(asm: SpecificationAssembler) -> None:
    c = asm.model.concept
    p = asm.schema_provenance("edge-application")
    for motion in ("draw", "thrust", "down", "scrape"):
        asm.add_operation(
            f"{motion}_motion_{c}",
            (),
            "motion",
            "constant",
            f"constant:{motion}_motion",
            p,
        )
    for action, motion in (
        ("slice", "draw"),
        ("pierce", "thrust"),
        ("chop", "down"),
        ("scrape", "scrape"),
    ):
        name = f"{action}_{c}"
        asm.add_operation(
            name,
            ("use_configuration", "force"),
            "use_outcome",
            "transformation",
            f"capability:{action}",
            p,
        )
        asm.add_axiom(
            f"{action}_definition",
            f"(forall ((cfg use_configuration) (f force)) (= ({name} cfg f) (apply_{c} cfg {motion}_motion_{c} f)))",
            (name, f"apply_{c}", f"{motion}_motion_{c}"),
            p,
        )


def _transport(asm: SpecificationAssembler) -> None:
    c = asm.model.concept
    p = asm.schema_provenance("transport")
    asm.add_operation(
        f"transport_{c}",
        (c, "origin", "destination", "route"),
        "transport_state",
        "transformation",
        "capability:transport",
        p,
    )
    asm.add_operation(
        f"carry_{c}",
        (c, "cargo", "transport_state"),
        "transport_state",
        "transformation",
        "capability:carry",
        p,
    )
    for name, arguments in (
        ("TravelsFrom", (c, "origin")),
        ("TravelsTo", (c, "destination")),
        ("Carries", (c, "cargo")),
    ):
        asm.add_predicate(name, arguments, f"relation:{name}", p)
    asm.add_axiom(
        "transport_closure",
        f"(forall ((x {c}) (o origin) (d destination) (r route)) (closedUnder (transport_{c} x o d r) transport_state))",
        (f"transport_{c}",),
        p,
    )


def _containment(asm: SpecificationAssembler) -> None:
    c = asm.model.concept
    p = asm.schema_provenance("containment")
    asm.add_operation(
        f"insert_{c}",
        (c, "contained_object", "container_state"),
        "container_state",
        "transformation",
        "capability:insert",
        p,
    )
    asm.add_operation(
        f"remove_{c}",
        (c, "contained_object", "container_state"),
        "container_state",
        "transformation",
        "capability:remove",
        p,
    )
    asm.add_predicate(
        "Contains",
        (c, "contained_object"),
        "relation:Contains",
        p,
    )
    asm.add_axiom(
        "insert_remove",
        f"(forall ((x {c}) (o contained_object) (s container_state)) (= (remove_{c} x o (insert_{c} x o s)) s))",
        (f"remove_{c}", f"insert_{c}"),
        p,
    )


def _computation(asm: SpecificationAssembler) -> None:
    c = asm.model.concept
    p = asm.schema_provenance("computation")
    for name, inputs, output, role, key in (
        (f"initialize_{c}", (c, "program"), "computation_state", "constructor", "capability:initialize"),
        (f"compute_{c}", (c, "input_data", "computation_state"), "computation_state", "transformation", "capability:compute"),
        (f"observe_{c}", (c, "computation_state"), "output_data", "observer", "observer:output"),
    ):
        asm.add_operation(name, inputs, output, role, key, p)
    for name, arguments in (
        ("RunsProgram", (c, "program")),
        ("ReceivesInput", (c, "input_data")),
        ("ProducesOutput", (c, "output_data")),
    ):
        asm.add_predicate(name, arguments, f"relation:{name}", p)
    asm.add_axiom(
        "compute_closure",
        f"(forall ((x {c}) (i input_data) (s computation_state)) (closedUnder (compute_{c} x i s) computation_state))",
        (f"compute_{c}",),
        p,
    )


def _agent_action(asm: SpecificationAssembler, family: str = "agent-action") -> None:
    c = asm.model.concept
    p = asm.schema_provenance(family)
    asm.add_operation(
        f"perform_{c}",
        (c, "action", "process_state"),
        "process_state",
        "transformation",
        "capability:perform",
        p,
    )
    asm.add_operation(
        f"observe_behavior_{c}",
        (c, "process_state"),
        "behavior_outcome",
        "observer",
        "observer:behavior",
        p,
    )
    asm.add_predicate("ActsIn", (c, "context"), "relation:ActsIn", p)
    asm.add_axiom(
        "perform_closure",
        f"(forall ((x {c}) (a action) (s process_state)) (closedUnder (perform_{c} x a s) process_state))",
        (f"perform_{c}",),
        p,
    )


def _structural(asm: SpecificationAssembler) -> None:
    c = asm.model.concept
    p = asm.schema_provenance("structural-composition")
    asm.add_operation(
        f"assemble_{c}",
        (c, "part", "structure_state"),
        "structure_state",
        "transformation",
        "capability:assemble",
        p,
    )
    asm.add_operation(f"detach_{c}", (c, "part", "structure_state"), "structure_state", "transformation", "capability:detach", p)
    asm.add_predicate("HasPart", (c, "part"), "relation:HasPart", p)
    asm.add_predicate("MadeOf", (c, "material"), "relation:MadeOf", p)
    asm.add_axiom("assemble_detach", f"(forall ((x {c}) (p part) (s structure_state)) (= (detach_{c} x p (assemble_{c} x p s)) s))", (f"detach_{c}", f"assemble_{c}"), p)


def _spatial_container(asm: SpecificationAssembler) -> None:
    c, p = asm.model.concept, asm.schema_provenance("spatial-container")
    asm.add_operation(f"admit_{c}", (c, "occupant", "access_state"), "access_state", "transformation", "capability:admit", p)
    asm.add_operation(f"room_of_{c}", (c, "room_id"), "room", "observer", "observer:room", p)
    asm.add_operation(f"close_{c}", (c, "access_state"), "access_state", "transformation", "capability:close", p)
    asm.add_predicate("Shelters", (c, "occupant"), "relation:shelters", p)
    asm.add_predicate("HasRoom", (c, "room"), "relation:has_room", p)
    asm.add_predicate("LocatedAt", (c, "location"), "relation:located_at", p)
    asm.add_axiom("closed_rejects_admission", f"(operationLaw close_{c} (closedUnder close_{c} access_state))", (f"close_{c}",), p)


def _mathematical_structure(asm: SpecificationAssembler) -> None:
    c, p = asm.model.concept, asm.schema_provenance("mathematical-structure")
    asm.add_operation(f"identity_{c}", (c,), c, "observer", "observer:identity", p)
    asm.add_axiom("identity_law", f"(forall ((x {c})) (= (identity_{c} x) x))", (f"identity_{c}",), p)


def _analysis_limits(asm: SpecificationAssembler) -> None:
    c, p = asm.model.concept, asm.schema_provenance("analysis-and-limits")
    asm.add_operation(f"limit_at_{c}", ("real_function", "real", "approach_direction"), "extended_real", "observer", "observer:limit", p)
    asm.add_operation(f"left_direction_{c}", (), "approach_direction", "constant", "constant:left", p)
    asm.add_operation(f"right_direction_{c}", (), "approach_direction", "constant", "constant:right", p)
    asm.add_operation(f"constant_function_{c}", ("real",), "real_function", "constructor", "constructor:constant_function", p)
    asm.add_predicate("ConvergesAt", ("real_function", "real"), "relation:converges_at", p)
    asm.add_predicate("ApproachesFrom", ("real", "approach_direction"), "relation:approaches_from", p)
    asm.add_axiom("constant_limit", f"(forall ((v real) (x real) (d approach_direction)) (= (limit_at_{c} (constant_function_{c} v) x d) v))", (f"limit_at_{c}", f"constant_function_{c}"), p)


def _generic_family(asm: SpecificationAssembler, family: str) -> None:
    c = asm.model.concept
    p = asm.schema_provenance(family)
    profiles = {
        "taxonomic-interface": (
            ("classification_context",),
            "taxonomic_kind",
            "classify",
            "observer:classification",
            "ClassifiedIn",
        ),
        "descriptive-observation": (
            ("property", "observation_context"),
            "property_value",
            "observe_property",
            "observer:property",
            "HasProperty",
        ),
        "risk-management": (
            ("hazard_context",),
            "risk_state",
            "assess_risk",
            "observer:risk",
            "MayCause",
        ),
        "state-lifecycle": (
            ("state", "event"),
            "state",
            "transition",
            "transformation:state",
            "HasState",
        ),
        "prerequisite-action": (
            ("precondition", "action_state"),
            "action_state",
            "enable",
            "transformation:enable",
            "Requires",
        ),
        "spatial-state": (
            ("spatial_context",),
            "location",
            "locate",
            "observer:location",
            "LocatedAt",
        ),
        "value-assessment": (
            ("assessment_context",),
            "assessed_value",
            "assess_value",
            "observer:value",
            "HasAssessedValue",
        ),
        "communication": (
            ("message", "social_state"),
            "social_state",
            "communicate",
            "transformation:communicate",
            "CommunicatesWith",
        ),
        "perception": (
            ("sensory_input",),
            "experience_state",
            "perceive",
            "observer:perception",
            "Perceives",
        ),
        "material-transformation": (
            ("material_state",),
            "material_state",
            "transform_material",
            "transformation:material",
            "TransformsMaterial",
        ),
    }
    inputs, output, stem, semantic_key, predicate = profiles[family]
    operation_name = f"{stem}_{c}"
    asm.add_operation(
        operation_name,
        (c, *inputs),
        output,
        "observer" if semantic_key.startswith("observer:") else "transformation",
        semantic_key,
        p,
    )
    relation_sort = inputs[0]
    asm.add_predicate(
        predicate,
        (c, relation_sort),
        f"relation:{predicate}",
        p,
    )
    asm.add_axiom(
        f"{stem}_closure",
        f"(operationLaw {operation_name} (closedUnder {operation_name} {output}))",
        (operation_name,),
        p,
    )


COMPILERS = {
    "functional-interface": _functional,
    "edge-application": _edge_application,
    "transport": _transport,
    "containment": _containment,
    "computation": _computation,
    "agent-action": _agent_action,
    "structural-composition": _structural,
    "spatial-container": _spatial_container,
    "mathematical-structure": _mathematical_structure,
    "analysis-and-limits": _analysis_limits,
}


def compile_model(
    model: ConceptModel,
    ontology: OntologyRegistry,
) -> AlgebraicSpecification:
    asm = SpecificationAssembler(model, ontology)
    if model.formal_operations:
        provenance = lambda support, confidence: (Provenance(ProvenanceKind.LLM_PROPOSED, "structured-semantic-stage", tuple(support), confidence),)
        for sort in model.formal_sorts:
            asm.add_sort(sort, provenance((model.sense or model.concept_kind,), .5))
        asm.add_sort(model.concept, provenance((model.sense or model.concept_kind,), .5))
        for operation in model.formal_operations:
            asm.add_operation(operation.name, operation.inputs, operation.output, operation.role, operation.semantic_key, provenance(operation.support, operation.confidence))
        for predicate in model.formal_predicates:
            asm.add_predicate(predicate.name, predicate.arguments, predicate.semantic_key, provenance(predicate.support, predicate.confidence))
        for axiom in model.formal_axioms:
            asm.add_axiom(axiom.name, axiom.expression, axiom.referenced_operations, provenance(axiom.support, axiom.confidence))
        return asm.finish()
    for family in ontology.dependency_closure(model.schema_families):
        compiler = COMPILERS.get(family)
        if compiler:
            compiler(asm)
        else:
            _generic_family(asm, family)

    # Evidence- and LLM-derived relations remain explicit and retain their own
    # provenance rather than inheriting schema confidence.
    for relation in model.relations:
        provenance = tuple(relation.provenance)
        asm.add_predicate(
            relation.predicate,
            (relation.subject_sort, relation.object_sort),
            f"relation:{relation.predicate}:{relation.object_value or relation.object_sort}",
            provenance,
        )

    # Unknown capabilities proposed or grounded outside a selected family are
    # still compiled as typed transformations, never as predicates.
    declared_capability_keys = {
        operation.semantic_key
        for operation in asm._operations.values()
    }
    for capability in model.capabilities:
        semantic_key = f"capability:{capability.action}"
        if semantic_key in declared_capability_keys:
            continue
        asm.add_operation(
            f"{capability.action}_{model.concept}",
            (model.concept, *capability.participant_roles, capability.input_sort),
            capability.output_sort,
            "transformation",
            semantic_key,
            tuple(capability.provenance),
        )

    return asm.finish()
