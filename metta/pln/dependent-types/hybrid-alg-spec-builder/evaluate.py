#!/usr/bin/env python3
"""Run a report-oriented evaluation of the standalone hybrid builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_hybrid_builder import builder
from test_stratified_evaluation import CASES


def evaluate() -> dict:
    cases = {}
    totals = {
        "sorts": 0,
        "operations": 0,
        "predicates": 0,
        "axioms": 0,
        "errors": 0,
        "operation_predicate_overlaps": 0,
    }
    grounded_features = 0
    all_features = 0

    for concept, perspective in CASES:
        result = builder().build(concept, perspective)
        spec = result.specification
        operation_keys = {item.semantic_key for item in spec.operations}
        predicate_keys = {item.semantic_key for item in spec.predicates}
        overlaps = len(operation_keys & predicate_keys)
        collections = (spec.sorts, spec.operations, spec.predicates, spec.axioms)
        features = [item for collection in collections for item in collection]
        grounded = sum(
            any(
                source.kind.value
                in {"direct-evidence", "schema-implied", "human-approved"}
                for source in item.provenance
            )
            for item in features
        )
        grounded_features += grounded
        all_features += len(features)
        counts = {
            "sorts": len(spec.sorts),
            "operations": len(spec.operations),
            "predicates": len(spec.predicates),
            "axioms": len(spec.axioms),
        }
        for name, count in counts.items():
            totals[name] += count
        totals["errors"] += sum(
            issue.severity == "error" for issue in result.issues
        )
        totals["operation_predicate_overlaps"] += overlaps
        cases[f"{concept}:{perspective}"] = {
            "valid": result.valid,
            "schemas": spec.schema_families,
            "counts": counts,
            "issues": [
                {
                    "code": issue.code,
                    "detail": issue.detail,
                    "severity": issue.severity,
                }
                for issue in result.issues
            ],
        }

    report = {
        "passed": (
            totals["errors"] == 0
            and totals["operation_predicate_overlaps"] == 0
        ),
        "case_count": len(CASES),
        "totals": totals,
        "grounded_or_schema_implied_ratio": (
            grounded_features / all_features if all_features else 1.0
        ),
        "cases": cases,
    }
    house = builder().build("house", "functional_use", "residential building for habitation").specification
    limit = builder().build("limit", "functional_use", "mathematical limit of a real function").specification
    house_ops = {item.semantic_key for item in house.operations}
    limit_ops = {item.semantic_key for item in limit.operations}
    union = house_ops | limit_ops
    report["house_limit_operation_jaccard"] = len(house_ops & limit_ops) / len(union) if union else 1.0
    report["passed"] = report["passed"] and report["house_limit_operation_jaccard"] < 0.2
    return report


def main() -> None:
    report = evaluate()
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        totals = report["totals"]
        print(f"{status}: {report['case_count']} stratified hybrid queries")
        print(
            f"{totals['sorts']} sorts, {totals['operations']} operations, "
            f"{totals['predicates']} predicates, {totals['axioms']} axioms"
        )
        print(
            f"{totals['errors']} validation errors, "
            f"{totals['operation_predicate_overlaps']} operation/predicate overlaps"
        )
        print(
            "grounded or schema-implied: "
            f"{report['grounded_or_schema_implied_ratio']:.1%}"
        )
        print(f"house/limit operation Jaccard: {report['house_limit_operation_jaccard']:.3f}")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
