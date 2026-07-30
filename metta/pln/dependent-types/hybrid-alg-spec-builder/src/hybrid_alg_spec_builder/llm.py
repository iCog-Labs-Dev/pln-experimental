"""Constrained structured-LLM helper interfaces.

The LLM proposes semantic IR only. It never emits trusted algebraic syntax.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Protocol, TextIO

from openai import OpenAI, OpenAIError

from .models import (
    CapabilityFrame,
    FormalAxiom,
    FormalOperation,
    FormalPredicate,
    Provenance,
    ProvenanceKind,
    RelationFrame,
    SemanticProposal,
)


DEFAULT_OPENAI_MODEL = "gpt-5.4"


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMRequest:
    concept: str
    perspective: str
    evidence: tuple[dict[str, Any], ...]
    retrieved_schemas: tuple[tuple[str, float], ...]
    allowed_schema_families: tuple[str, ...]
    context: str = ""
    validation_issues: tuple[str, ...] = ()
    allowed_roles: tuple[str, ...] = (
        "agent",
        "instrument",
        "target",
        "resource",
        "input",
        "output",
        "context",
        "path",
        "state",
    )


class StructuredLLM(Protocol):
    @property
    def model_id(self) -> str: ...

    def propose(self, request: LLMRequest) -> SemanticProposal: ...


class NullLLM:
    model_id = "none"

    def propose(self, request: LLMRequest) -> SemanticProposal:
        return SemanticProposal(notes=["LLM disabled"])


class StaticLLM:
    """Test/provider adapter returning a preconstructed proposal."""

    def __init__(self, proposal: SemanticProposal, model_id: str = "static"):
        self._proposal = proposal
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def propose(self, request: LLMRequest) -> SemanticProposal:
        return self._proposal


def _identifier(value: Any) -> str | None:
    text = str(value).strip().replace("-", "_")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
        return None
    return text


def proposal_from_dict(
    value: dict[str, Any],
    request: LLMRequest,
    model_id: str,
) -> SemanticProposal:
    allowed_families = set(request.allowed_schema_families)
    allowed_roles = set(request.allowed_roles)
    families = [
        str(name)
        for name in value.get("schema_families", ())
        if str(name) in allowed_families
    ]
    capabilities: list[CapabilityFrame] = []
    relations: list[RelationFrame] = []
    sorts = [name for raw in value.get("sorts", ()) if (name := _identifier(raw))]
    operations: list[FormalOperation] = []
    predicates: list[FormalPredicate] = []
    axioms: list[FormalAxiom] = []
    for item in value.get("operations", ()):
        name = _identifier(item.get("name", ""))
        inputs = tuple(x for raw in item.get("inputs", ()) if (x := _identifier(raw)))
        output = _identifier(item.get("output", ""))
        role = str(item.get("role", "transformation"))
        key = _identifier(item.get("semantic_key", ""))
        if name and output and key and role in {"constructor", "transformation", "observer", "constant", "combinator"}:
            operations.append(FormalOperation(name, inputs, output, role, f"operation:{key}", tuple(map(str, item.get("support", ()))), min(.55, float(item.get("confidence", .5)))))
    for item in value.get("predicates", ()):
        name = _identifier(item.get("name", ""))
        arguments = tuple(x for raw in item.get("arguments", ()) if (x := _identifier(raw)))
        key = _identifier(item.get("semantic_key", ""))
        if name and arguments and key and not name.lower().startswith(("can", "usefor", "usedfor")):
            predicates.append(FormalPredicate(name, arguments, f"relation:{key}", tuple(map(str, item.get("support", ()))), min(.55, float(item.get("confidence", .5)))))
    operation_names = {item.name for item in operations}
    for item in value.get("axioms", ()):
        name = _identifier(item.get("name", ""))
        expression = str(item.get("expression", "")).strip()
        refs = tuple(x for raw in item.get("referenced_operations", ()) if (x := _identifier(raw)) and x in operation_names)
        if name and expression.startswith("(") and expression.endswith(")") and refs and re.fullmatch(r"[A-Za-z0-9_()=<>+*/.,\-\s]+", expression):
            axioms.append(FormalAxiom(name, expression, refs, tuple(map(str, item.get("support", ()))), min(.55, float(item.get("confidence", .5)))))

    for item in value.get("capabilities", ()):
        action = _identifier(item.get("action", ""))
        family = str(item.get("family", "")).strip()
        roles = tuple(
            str(role)
            for role in item.get("participant_roles", ())
            if str(role) in allowed_roles
        )
        input_sort = _identifier(item.get("input_sort", "input_state"))
        output_sort = _identifier(item.get("output_sort", "output_state"))
        if (
            not action
            or not input_sort
            or not output_sort
            or family not in allowed_families
            or not roles
        ):
            continue
        confidence = min(max(float(item.get("confidence", 0.45)), 0.0), 0.55)
        capabilities.append(
            CapabilityFrame(
                action=action,
                family=family,
                participant_roles=roles,
                input_sort=input_sort,
                output_sort=output_sort,
                provenance=[
                    Provenance(
                        ProvenanceKind.LLM_PROPOSED,
                        model_id,
                        tuple(str(entry) for entry in item.get("support", ())),
                        confidence,
                    )
                ],
            )
        )

    for item in value.get("relations", ()):
        predicate = _identifier(item.get("predicate", ""))
        subject_sort = _identifier(item.get("subject_sort", request.concept))
        object_sort = _identifier(item.get("object_sort", ""))
        if (
            not predicate
            or not subject_sort
            or not object_sort
            or predicate in {"CapableOf", "UsedFor"}
            or predicate.lower().startswith("can")
        ):
            continue
        confidence = min(max(float(item.get("confidence", 0.4)), 0.0), 0.55)
        relations.append(
            RelationFrame(
                predicate=predicate,
                subject_sort=subject_sort,
                object_sort=object_sort,
                object_value=item.get("object_value"),
                provenance=[
                    Provenance(
                        ProvenanceKind.LLM_PROPOSED,
                        model_id,
                        tuple(str(entry) for entry in item.get("support", ())),
                        confidence,
                    )
                ],
            )
        )

    return SemanticProposal(
        concept_kind=str(value.get("concept_kind", "unknown")),
        sense=str(value.get("sense", "")),
        schema_families=families,
        sorts=sorts,
        operations=operations,
        predicates=predicates,
        axioms=axioms,
        capabilities=capabilities,
        relations=relations,
        notes=[str(note) for note in value.get("notes", ())],
    )


def _system_prompt() -> str:
    return (
        "You are a semantic-frame inducer for an algebraic specification system. "
        "Infer the requested sense and create a concept-specific many-sorted algebraic specification. "
        "Never copy a generic tool-use signature merely because the perspective is functional_use. "
        "Operations are constructors, transformations, observers, constants, or combinators. "
        "Predicates express static relations only and must not restate capabilities. Axioms must be "
        "well-typed S-expressions using only declared operations. Prefer domain laws over closure placeholders."
    )


def _user_prompt(request: LLMRequest) -> str:
    contract = {
        "concept_kind": "domain category",
        "sense": "resolved meaning in the supplied context",
        "schema_families": ["one allowed family"],
        "sorts": ["domain_sort"],
        "operations": [
            {
                "name": "typed_operation",
                "inputs": ["domain_sort"],
                "output": "codomain_sort",
                "role": "transformation",
                "semantic_key": "unique_operation_meaning",
                "support": ["evidence ids or analogy"],
                "confidence": 0.0,
            }
        ],
        "predicates": [
            {
                "name": "StaticRelation",
                "arguments": [request.concept, "related_sort"],
                "semantic_key": "unique_relation_meaning",
                "support": ["evidence ids or analogy"],
                "confidence": 0.0,
            }
        ],
        "axioms": [{"name": "law_name", "expression": "(forall (...) (= (...) (...)))", "referenced_operations": ["typed_operation"], "support": ["domain law"], "confidence": 0.0}],
        "notes": [],
    }
    payload = {
        "concept": request.concept,
        "perspective": request.perspective,
        "context": request.context,
        "evidence": request.evidence,
        "retrieved_schemas": request.retrieved_schemas,
        "allowed_schema_families": request.allowed_schema_families,
        "allowed_roles": request.allowed_roles,
        "validation_issues_from_previous_attempt": request.validation_issues,
        "output_contract": contract,
    }
    return json.dumps(payload, sort_keys=True)


class OpenAILLM:
    """OpenAI Responses API adapter using strict Structured Outputs."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        timeout: float = 45.0,
        base_url: str | None = None,
        client: Any | None = None,
        trace: bool = False,
        trace_stream: TextIO | None = None,
    ):
        self.model = model
        self.trace = trace
        self.trace_stream = trace_stream or sys.stderr
        self.client = client or OpenAI(
            api_key=api_key,
            timeout=timeout,
            base_url=base_url,
        )

    @property
    def model_id(self) -> str:
        return self.model

    def propose(self, request: LLMRequest) -> SemanticProposal:
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "concept_kind": {"type": "string"}, "sense": {"type": "string"},
                "schema_families": {"type": "array", "items": {"type": "string"}},
                "sorts": {"type": "array", "items": {"type": "string"}},
                "operations": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
                    "name": {"type": "string"}, "inputs": {"type": "array", "items": {"type": "string"}}, "output": {"type": "string"},
                    "role": {"type": "string", "enum": ["constructor", "transformation", "observer", "constant", "combinator"]},
                    "semantic_key": {"type": "string"}, "support": {"type": "array", "items": {"type": "string"}}, "confidence": {"type": "number"}},
                    "required": ["name", "inputs", "output", "role", "semantic_key", "support", "confidence"]}},
                "predicates": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
                    "name": {"type": "string"}, "arguments": {"type": "array", "items": {"type": "string"}}, "semantic_key": {"type": "string"},
                    "support": {"type": "array", "items": {"type": "string"}}, "confidence": {"type": "number"}},
                    "required": ["name", "arguments", "semantic_key", "support", "confidence"]}},
                "axioms": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
                    "name": {"type": "string"}, "expression": {"type": "string"}, "referenced_operations": {"type": "array", "items": {"type": "string"}},
                    "support": {"type": "array", "items": {"type": "string"}}, "confidence": {"type": "number"}},
                    "required": ["name", "expression", "referenced_operations", "support", "confidence"]}},
                "notes": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["concept_kind", "sense", "schema_families", "sorts", "operations", "predicates", "axioms", "notes"]
        }
        instructions = _system_prompt()
        user_input = _user_prompt(request)
        if self.trace:
            print("\n===== OPENAI LLM REQUEST =====", file=self.trace_stream)
            print(f"model: {self.model}", file=self.trace_stream)
            print("----- instructions -----", file=self.trace_stream)
            print(instructions, file=self.trace_stream)
            print("----- input -----", file=self.trace_stream)
            print(user_input, file=self.trace_stream)
            print("===== END OPENAI LLM REQUEST =====", file=self.trace_stream)
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=user_input,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "algebraic_spec_ir",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )
            raw_output = response.output_text
            if self.trace:
                print("\n===== OPENAI LLM RESPONSE =====", file=self.trace_stream)
                print(raw_output, file=self.trace_stream)
                print("===== END OPENAI LLM RESPONSE =====", file=self.trace_stream)
            value = json.loads(raw_output)
        except (
            OpenAIError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise LLMError(f"Structured LLM request failed: {error}") from error
        if not isinstance(value, dict):
            raise LLMError("Structured LLM response must be a JSON object")
        return proposal_from_dict(value, request, self.model)


# Compatibility for integrations using the original standalone class name.
OpenAICompatibleLLM = OpenAILLM
