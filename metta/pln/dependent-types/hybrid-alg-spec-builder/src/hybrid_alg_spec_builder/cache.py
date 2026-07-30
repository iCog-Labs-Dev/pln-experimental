"""SQLite cache for validated generated specifications."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import (
    AlgebraicSpecification,
    AxiomDecl,
    OperationDecl,
    PredicateDecl,
    Provenance,
    ProvenanceKind,
    SortDecl,
)


def _provenance(value: dict) -> Provenance:
    return Provenance(
        ProvenanceKind(value["kind"]),
        value["source"],
        tuple(value.get("support", ())),
        float(value.get("confidence", 0.5)),
    )


def specification_from_dict(value: dict) -> AlgebraicSpecification:
    return AlgebraicSpecification(
        concept=value["concept"],
        perspective=value["perspective"],
        sorts=[
            SortDecl(
                item["name"],
                tuple(_provenance(entry) for entry in item["provenance"]),
                float(item["confidence"]),
            )
            for item in value.get("sorts", ())
        ],
        operations=[
            OperationDecl(
                item["name"],
                tuple(item["inputs"]),
                item["output"],
                item["role"],
                item["semantic_key"],
                tuple(_provenance(entry) for entry in item["provenance"]),
                float(item["confidence"]),
            )
            for item in value.get("operations", ())
        ],
        predicates=[
            PredicateDecl(
                item["name"],
                tuple(item["arguments"]),
                item["semantic_key"],
                tuple(_provenance(entry) for entry in item["provenance"]),
                float(item["confidence"]),
            )
            for item in value.get("predicates", ())
        ],
        axioms=[
            AxiomDecl(
                item["name"],
                item["expression"],
                tuple(item["referenced_operations"]),
                tuple(_provenance(entry) for entry in item["provenance"]),
                float(item["confidence"]),
            )
            for item in value.get("axioms", ())
        ],
        schema_families=list(value.get("schema_families", ())),
        ontology_version=value.get("ontology_version", "1"),
        evidence_digest=value.get("evidence_digest", ""),
    )


class SpecificationCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS specifications (
                    concept TEXT NOT NULL,
                    perspective TEXT NOT NULL,
                    ontology_version TEXT NOT NULL,
                    evidence_digest TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    specification_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (
                        concept,
                        perspective,
                        ontology_version,
                        evidence_digest,
                        model_id
                    )
                )
                """
            )

    def get(
        self,
        concept: str,
        perspective: str,
        ontology_version: str,
        evidence_digest: str,
        model_id: str,
    ) -> AlgebraicSpecification | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT specification_json
                FROM specifications
                WHERE concept = ?
                  AND perspective = ?
                  AND ontology_version = ?
                  AND evidence_digest = ?
                  AND model_id = ?
                """,
                (
                    concept,
                    perspective,
                    ontology_version,
                    evidence_digest,
                    model_id,
                ),
            ).fetchone()
        if row is None:
            return None
        return specification_from_dict(json.loads(row[0]))

    def put(self, specification: AlgebraicSpecification, model_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO specifications (
                    concept,
                    perspective,
                    ontology_version,
                    evidence_digest,
                    model_id,
                    specification_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    specification.concept,
                    specification.perspective,
                    specification.ontology_version,
                    specification.evidence_digest,
                    model_id,
                    specification.to_json(indent=None),
                ),
            )
