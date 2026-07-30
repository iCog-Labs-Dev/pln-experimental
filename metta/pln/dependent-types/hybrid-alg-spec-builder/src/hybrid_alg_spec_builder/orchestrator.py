"""End-to-end hybrid evidence/retrieval/LLM/logic orchestration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from .cache import SpecificationCache
from .compiler import compile_model
from .embeddings import SchemaRetriever
from .evidence import EvidenceStore, safe_symbol
from .grounding import build_grounded_model, merge_proposal
from .llm import LLMError, LLMRequest, NullLLM, StructuredLLM
from .models import BuildResult
from .ontology import OntologyRegistry
from .validation import validate_specification


class HybridAlgebraicSpecBuilder:
    def __init__(
        self,
        evidence_store: EvidenceStore,
        ontology: OntologyRegistry | None = None,
        retriever: SchemaRetriever | None = None,
        llm: StructuredLLM | None = None,
        cache: SpecificationCache | None = None,
        llm_mode: str = "missing",
        evidence_limit: int = 100,
        retrieval_top_k: int = 5,
        include_incoming_evidence: bool = False,
    ):
        if llm_mode not in {"off", "missing", "always"}:
            raise ValueError("llm_mode must be off, missing, or always")
        self.evidence_store = evidence_store
        self.ontology = ontology or OntologyRegistry()
        self.retriever = retriever or SchemaRetriever(self.ontology)
        self.llm = llm or NullLLM()
        self.cache = cache
        self.llm_mode = llm_mode
        self.evidence_limit = evidence_limit
        self.retrieval_top_k = retrieval_top_k
        self.include_incoming_evidence = include_incoming_evidence

    def _should_use_llm(self, model) -> bool:
        if self.llm_mode == "off" or isinstance(self.llm, NullLLM):
            return False
        if self.llm_mode == "always":
            return True
        return not model.capabilities or len(model.schema_families) <= 1

    def build(self, concept: str, perspective: str, context: str = "") -> BuildResult:
        concept = safe_symbol(concept)
        perspective = perspective.replace("-", "_")
        evidence = self.evidence_store.for_concept(
            concept,
            include_incoming=self.include_incoming_evidence,
            limit=self.evidence_limit,
        )
        evidence_text = context + " " + " ".join(
            f"{fact.relation} {fact.source} {fact.target} {fact.surface_text}"
            for fact in evidence
        )
        hits = self.retriever.retrieve(
            concept,
            perspective,
            evidence_text,
            top_k=self.retrieval_top_k,
        )
        model = build_grounded_model(
            concept,
            perspective,
            evidence,
            hits,
            self.ontology,
        )
        model.sense = context
        model_id = self.llm.model_id if self._should_use_llm(model) else "none"
        digest = model.evidence_digest()
        if self.cache:
            cached = self.cache.get(
                concept,
                perspective,
                self.ontology.version,
                digest,
                model_id,
            )
            if cached:
                issues = validate_specification(cached, self.ontology)
                return BuildResult(
                    cached,
                    issues,
                    cache_hit=True,
                    used_llm=model_id != "none",
                    retrieved_schemas=[
                        (hit.name, hit.score)
                        for hit in hits
                    ],
                )

        used_llm = False
        deterministic_model = deepcopy(model)
        if self._should_use_llm(model):
            request = LLMRequest(
                concept,
                perspective,
                tuple(
                    {
                        "id": fact.evidence_id,
                        "relation": fact.relation,
                        "source": fact.source,
                        "target": fact.target,
                        "weight": fact.weight,
                    }
                    for fact in evidence
                ),
                tuple((hit.name, hit.score) for hit in hits),
                tuple(
                    family.name
                    for family in self.ontology.allowed_for(perspective)
                ),
                context=context,
            )
            try:
                proposal = self.llm.propose(request)
                merge_proposal(model, proposal, self.ontology)
                used_llm = True
            except LLMError:
                model = deterministic_model

        specification = compile_model(model, self.ontology)
        issues = validate_specification(specification, self.ontology)

        # Invalid LLM enrichment never poisons the cache or caller result.
        if used_llm and any(issue.severity == "error" for issue in issues):
            repair_model = deepcopy(deterministic_model)
            try:
                repair_request = replace(request, validation_issues=tuple(f"{issue.code}: {issue.detail}" for issue in issues))
                merge_proposal(repair_model, self.llm.propose(repair_request), self.ontology)
                repaired = compile_model(repair_model, self.ontology)
                repaired_issues = validate_specification(repaired, self.ontology)
                if not any(issue.severity == "error" for issue in repaired_issues):
                    model, specification, issues = repair_model, repaired, repaired_issues
                else:
                    raise LLMError("repair remained invalid")
            except LLMError:
                model = deterministic_model
                specification = compile_model(model, self.ontology)
                issues = validate_specification(specification, self.ontology)
                used_llm = False
                model_id = "none"

        result = BuildResult(
            specification,
            issues,
            cache_hit=False,
            used_llm=used_llm,
            retrieved_schemas=[(hit.name, hit.score) for hit in hits],
        )
        if result.valid and self.cache:
            self.cache.put(specification, model_id)
        return result
