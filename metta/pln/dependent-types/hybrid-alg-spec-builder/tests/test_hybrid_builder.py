from __future__ import annotations

import tempfile
import unittest
import json
import io
from pathlib import Path
from types import SimpleNamespace

from hybrid_alg_spec_builder.cache import SpecificationCache
from hybrid_alg_spec_builder.embeddings import HashEmbeddingProvider, OpenAIEmbeddingProvider, SchemaRetriever
from hybrid_alg_spec_builder.evidence import EvidenceStore, SQLiteEvidenceStore
from hybrid_alg_spec_builder.llm import LLMRequest, OpenAILLM, StaticLLM, proposal_from_dict
from hybrid_alg_spec_builder.models import (
    CapabilityFrame,
    EvidenceFact,
    Provenance,
    ProvenanceKind,
    RelationFrame,
    SemanticProposal,
    FormalAxiom,
    FormalOperation,
    FormalPredicate,
)
from hybrid_alg_spec_builder.ontology import OntologyRegistry
from hybrid_alg_spec_builder.orchestrator import HybridAlgebraicSpecBuilder
from hybrid_alg_spec_builder.prototypes import DEFAULT_PROTOTYPES
from hybrid_alg_spec_builder.serializers import to_metta, to_readable


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "concepts.metta"


def builder(
    *,
    llm=None,
    llm_mode="off",
    cache=None,
):
    evidence = EvidenceStore.from_paths([FIXTURE])
    ontology = OntologyRegistry()
    retriever = SchemaRetriever(
        ontology,
        HashEmbeddingProvider(),
        DEFAULT_PROTOTYPES,
    )
    return HybridAlgebraicSpecBuilder(
        evidence,
        ontology=ontology,
        retriever=retriever,
        llm=llm,
        llm_mode=llm_mode,
        cache=cache,
    )


class HybridBuilderTests(unittest.TestCase):
    def test_official_sdk_responses_and_embeddings_are_used(self):
        class Responses:
            kwargs = None

            def create(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(output_text=json.dumps({
                    "concept_kind": "mathematical-object",
                    "sense": "equation over real numbers",
                    "schema_families": ["mathematical-structure"],
                    "sorts": ["equation", "real"],
                    "operations": [{"name": "solve", "inputs": ["equation"], "output": "real", "role": "observer", "semantic_key": "solve", "support": ["domain-model"], "confidence": 0.5}],
                    "predicates": [], "axioms": [], "notes": [],
                }))

        class Embeddings:
            kwargs = None

            def create(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(data=[
                    SimpleNamespace(index=1, embedding=[0.0, 1.0]),
                    SimpleNamespace(index=0, embedding=[1.0, 0.0]),
                ])

        responses, embeddings = Responses(), Embeddings()
        client = SimpleNamespace(responses=responses, embeddings=embeddings)
        request = LLMRequest("equation", "functional_use", (), (), ("mathematical-structure",), context="an equation over real numbers")
        trace = io.StringIO()
        proposal = OpenAILLM("unused", "gpt-5.4", client=client, trace=True, trace_stream=trace).propose(request)
        vectors = OpenAIEmbeddingProvider("unused", client=client).embed(["a", "b"])
        self.assertEqual("gpt-5.4", responses.kwargs["model"])
        self.assertEqual("json_schema", responses.kwargs["text"]["format"]["type"])
        self.assertEqual("text-embedding-3-small", embeddings.kwargs["model"])
        self.assertEqual([[1.0, 0.0], [0.0, 1.0]], vectors)
        self.assertEqual("solve", proposal.operations[0].name)
        self.assertIn("===== OPENAI LLM REQUEST =====", trace.getvalue())
        self.assertIn('"concept": "equation"', trace.getvalue())
        self.assertIn("===== OPENAI LLM RESPONSE =====", trace.getvalue())

    def test_disk_index_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteEvidenceStore.build(Path(directory) / "evidence.sqlite3", [FIXTURE])
            self.assertEqual(5, len(store.for_concept("knife")))

    def test_formal_ir_is_concept_specific_and_not_tool_template(self):
        provenance = ("domain-model",)
        house = SemanticProposal(
            concept_kind="building", sense="dwelling and shelter", schema_families=["spatial-container"],
            sorts=["house", "occupant", "room", "access_state"],
            operations=[FormalOperation("enter_house", ("house", "occupant", "access_state"), "access_state", "transformation", "enter", provenance)],
            predicates=[FormalPredicate("Shelters", ("house", "occupant"), "shelters", provenance)],
            axioms=[FormalAxiom("entry_preserves_house", "(forall ((h house) (o occupant) (s access_state)) (= (enter_house h o s) (enter_house h o s)))", ("enter_house",), provenance)],
        )
        limit = SemanticProposal(
            concept_kind="mathematical-object", sense="limit of a real function", schema_families=["mathematical-structure", "analysis-and-limits"],
            sorts=["limit", "real", "real_function", "approach_direction"],
            operations=[FormalOperation("evaluate_limit", ("real_function", "real", "approach_direction"), "limit", "observer", "evaluate_limit", provenance)],
            predicates=[FormalPredicate("ConvergesAt", ("real_function", "real"), "converges_at", provenance)],
            axioms=[FormalAxiom("constant_limit", "(forall ((f real_function) (x real) (d approach_direction)) (= (evaluate_limit f x d) (evaluate_limit f x d)))", ("evaluate_limit",), provenance)],
        )
        house_spec = builder(llm=StaticLLM(house), llm_mode="always").build("house", "functional_use", "a residential building").specification
        limit_spec = builder(llm=StaticLLM(limit), llm_mode="always").build("limit", "functional_use", "the mathematical limit of a real function").specification
        house_ops = {item.name for item in house_spec.operations}
        limit_ops = {item.name for item in limit_spec.operations}
        self.assertFalse(house_ops & limit_ops)
        self.assertNotIn("motion", {item.name for item in house_spec.sorts + limit_spec.sorts})
        self.assertIn("enter_house", house_ops)
        self.assertIn("evaluate_limit", limit_ops)

    def test_evidence_parser_indexes_concepts(self):
        store = EvidenceStore.from_paths([FIXTURE])
        facts = store.for_concept("knife")
        self.assertEqual(5, len(facts))
        self.assertEqual(
            {"isA", "UsedFor", "hasproperty", "Causes"},
            {fact.relation for fact in facts},
        )

    def test_incoming_capability_is_not_assigned_to_target_concept(self):
        store = EvidenceStore.from_paths([FIXTURE])
        ontology = OntologyRegistry()
        incoming = EvidenceFact("CapableOf", "fork", "cut", 2.0)
        store.add(incoming)
        hybrid = HybridAlgebraicSpecBuilder(
            store,
            ontology=ontology,
            retriever=SchemaRetriever(
                ontology,
                HashEmbeddingProvider(),
                DEFAULT_PROTOTYPES,
            ),
            llm_mode="off",
        )
        result = hybrid.build("cut", "functional_use")
        all_features = (
            result.specification.sorts
            + result.specification.operations
            + result.specification.predicates
            + result.specification.axioms
        )
        self.assertFalse(
            any(
                source.source == incoming.evidence_id
                for feature in all_features
                for source in feature.provenance
            )
        )

    def test_offline_knife_build_is_rich_and_separated(self):
        result = builder().build("knife", "functional_use")
        self.assertTrue(result.valid, result.issues)
        self.assertFalse(result.used_llm)
        self.assertIn("edge-application", result.specification.schema_families)
        operation_names = {
            item.name for item in result.specification.operations
        }
        predicate_names = {
            item.name for item in result.specification.predicates
        }
        self.assertTrue(
            {"slice_knife", "pierce_knife", "chop_knife", "scrape_knife"}
            <= operation_names
        )
        self.assertNotIn("UsedFor", predicate_names)
        self.assertIn("ServesTask", predicate_names)
        operation_keys = {
            item.semantic_key for item in result.specification.operations
        }
        predicate_keys = {
            item.semantic_key for item in result.specification.predicates
        }
        self.assertFalse(operation_keys & predicate_keys)
        self.assertGreaterEqual(len(result.specification.sorts), 10)
        self.assertGreaterEqual(len(result.specification.axioms), 10)

    def test_llm_can_fill_a_missing_capability_through_ir(self):
        provenance = [
            Provenance(
                ProvenanceKind.LLM_PROPOSED,
                "test-model",
                ("analogy to cutting tools",),
                0.5,
            )
        ]
        proposal = SemanticProposal(
            schema_families=["edge-application"],
            capabilities=[
                CapabilityFrame(
                    "slice",
                    "edge-application",
                    ("agent", "target"),
                    "use_configuration",
                    "use_outcome",
                    provenance,
                )
            ],
            relations=[
                RelationFrame(
                    "CompatibleWith",
                    "mystery_blade",
                    "target",
                    None,
                    provenance,
                )
            ],
        )
        result = builder(
            llm=StaticLLM(proposal),
            llm_mode="always",
        ).build("mystery_blade", "functional_use")
        self.assertTrue(result.valid, result.issues)
        self.assertTrue(result.used_llm)
        self.assertIn("edge-application", result.specification.schema_families)
        llm_features = [
            item
            for item in result.specification.predicates
            if any(
                source.kind == ProvenanceKind.LLM_PROPOSED
                for source in item.provenance
            )
        ]
        self.assertTrue(llm_features)
        self.assertTrue(all(item.confidence <= 0.55 for item in llm_features))

    def test_forbidden_llm_family_is_discarded(self):
        proposal = SemanticProposal(
            schema_families=["computation"],
            capabilities=[
                CapabilityFrame(
                    "compute",
                    "computation",
                    ("input",),
                    "input_data",
                    "output_data",
                    [],
                )
            ],
        )
        result = builder(
            llm=StaticLLM(proposal),
            llm_mode="always",
        ).build("knife", "functional_use")
        # Computation is allowed for functional use, so exercise an actually
        # forbidden family by building a taxonomic query instead.
        taxonomic = builder(
            llm=StaticLLM(proposal),
            llm_mode="always",
        ).build("knife", "taxonomic_kind")
        self.assertTrue(result.valid)
        self.assertTrue(taxonomic.valid)
        self.assertNotIn("computation", taxonomic.specification.schema_families)
        self.assertNotIn(
            "compute_knife",
            {item.name for item in taxonomic.specification.operations},
        )

    def test_llm_json_contract_rejects_injection_and_capability_predicates(self):
        request = LLMRequest(
            "knife",
            "functional_use",
            (),
            (),
            ("functional-interface",),
        )
        proposal = proposal_from_dict(
            {
                "schema_families": ["functional-interface"],
                "capabilities": [
                    {
                        "action": "bad) (payload",
                        "family": "functional-interface",
                        "participant_roles": ["target"],
                        "input_sort": "input_state",
                        "output_sort": "output_state",
                    }
                ],
                "relations": [
                    {
                        "predicate": "CanCut",
                        "subject_sort": "knife",
                        "object_sort": "target",
                    },
                    {
                        "predicate": "bad) (payload",
                        "subject_sort": "knife",
                        "object_sort": "target",
                    },
                ],
            },
            request,
            "test-model",
        )
        self.assertFalse(proposal.capabilities)
        self.assertFalse(proposal.relations)

    def test_sqlite_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = SpecificationCache(Path(directory) / "specs.sqlite3")
            first = builder(cache=cache).build("car", "functional_use")
            second = builder(cache=cache).build("car", "functional_use")
            self.assertTrue(first.valid)
            self.assertFalse(first.cache_hit)
            self.assertTrue(second.cache_hit)
            self.assertEqual(
                first.specification.to_dict(),
                second.specification.to_dict(),
            )

    def test_serializers_preserve_declared_structure(self):
        result = builder().build("knife", "functional_use")
        readable = to_readable(result.specification)
        metta = to_metta(result.specification)
        self.assertIn("spec KNIFE_FUNCTIONAL_USE", readable)
        self.assertIn("pierce_knife", readable)
        self.assertIn("(has_operation", metta)
        self.assertIn("(operation_signature", metta)


if __name__ == "__main__":
    unittest.main()
