from __future__ import annotations

import unittest

from test_hybrid_builder import builder


CASES = (
    ("knife", "functional_use"),
    ("car", "functional_use"),
    ("box", "functional_use"),
    ("computer", "information_computational"),
    ("human", "behavioral_process"),
    ("theorem", "structural_composition"),
    ("house", "safety_risk"),
    ("house", "functional_use"),
    ("limit", "functional_use"),
    ("school", "spatial_context"),
    ("socialize", "causal_prerequisite"),
    ("knife", "taxonomic_kind"),
    ("unknown", "descriptive_property"),
)


class StratifiedEvaluationTests(unittest.TestCase):
    def test_unrelated_domains_do_not_collapse_to_one_signature(self):
        house = builder().build("house", "functional_use", "residential building for habitation")
        limit = builder().build("limit", "functional_use", "mathematical limit of a real function")
        house_ops = {item.semantic_key for item in house.specification.operations}
        limit_ops = {item.semantic_key for item in limit.specification.operations}
        union = house_ops | limit_ops
        jaccard = len(house_ops & limit_ops) / len(union) if union else 1.0
        self.assertLess(jaccard, 0.2)
        forbidden = {"motion", "force", "use_configuration", "use_outcome"}
        self.assertFalse(forbidden & {item.name for item in house.specification.sorts})
        self.assertFalse(forbidden & {item.name for item in limit.specification.sorts})

    def test_all_stratified_queries_are_valid(self):
        for concept, perspective in CASES:
            with self.subTest(concept=concept, perspective=perspective):
                result = builder().build(concept, perspective)
                self.assertTrue(result.valid, result.issues)
                self.assertTrue(result.specification.sorts)
                self.assertTrue(result.specification.operations)

    def test_provenance_is_present_on_every_feature(self):
        for concept, perspective in CASES:
            result = builder().build(concept, perspective)
            for collection in (
                result.specification.sorts,
                result.specification.operations,
                result.specification.predicates,
                result.specification.axioms,
            ):
                for feature in collection:
                    self.assertTrue(feature.provenance)


if __name__ == "__main__":
    unittest.main()
