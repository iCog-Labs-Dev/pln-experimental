"""ConceptNet-style MeTTa evidence ingestion and indexing."""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .models import EvidenceFact


RELATION_ALIASES = {
    name.lower(): canonical
    for canonical, names in {
        "isA": ("isA", "IsA"),
        "InstanceOf": ("InstanceOf", "instanceOf"),
        "hasproperty": ("hasproperty", "HasProperty", "hasProperty"),
        "hasPrerequisite": ("hasPrerequisite", "HasPrerequisite"),
        "hasSubevent": ("hasSubevent", "HasSubevent"),
        "UsedFor": ("UsedFor", "usedFor"),
        "CapableOf": ("CapableOf", "capableOf"),
        "ReceivesAction": ("ReceivesAction", "receivesAction"),
        "Causes": ("Causes", "causes"),
        "Entails": ("Entails", "entails"),
        "CausesDesire": ("CausesDesire", "causesDesire"),
        "HasA": ("HasA", "hasA"),
        "PartOf": ("PartOf", "partOf"),
        "MadeOf": ("MadeOf", "madeOf"),
        "AtLocation": ("AtLocation", "atLocation"),
        "LocatedNear": ("LocatedNear", "locatedNear"),
        "HasContext": ("HasContext", "hasContext"),
        "CreatedBy": ("CreatedBy", "createdBy"),
        "RelatedTo": ("RelatedTo", "relatedTo"),
        "Synonym": ("Synonym", "synonym"),
        "FormOf": ("FormOf", "formOf"),
        "DerivedFrom": ("DerivedFrom", "derivedFrom"),
        "DefinedBy": ("DefinedBy", "definedBy"),
        "DistinctFrom": ("DistinctFrom", "distinctFrom"),
        "Desires": ("Desires", "desires"),
    }.items()
    for name in names
}


def safe_symbol(value: str) -> str:
    value = value.strip("'\"()")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Za-z0-9_]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        return "unknown"
    if not re.match(r"[A-Za-z_]", value):
        return f"c_{value}"
    return value


def tokenize_atom(line: str) -> list[str] | None:
    text = line.strip()
    if not (text.startswith("(") and text.endswith(")")):
        return None
    text = text[1:-1].strip()
    tokens: list[str] = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        if text[index] in {"'", '"'}:
            quote = text[index]
            start = index
            index += 1
            escaped = False
            while index < len(text):
                char = text[index]
                if char == quote and not escaped:
                    index += 1
                    break
                escaped = char == "\\" and not escaped
                if char != "\\":
                    escaped = False
                index += 1
            tokens.append(text[start:index])
            continue
        if text[index] == "(":
            start = index
            depth = 0
            while index < len(text):
                if text[index] == "(":
                    depth += 1
                elif text[index] == ")":
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                index += 1
            tokens.append(text[start:index])
            continue
        start = index
        while index < len(text) and not text[index].isspace():
            index += 1
        tokens.append(text[start:index])
    return tokens


def _input_paths(paths: Iterable[str | Path]) -> Iterable[Path]:
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            yield from sorted(path.rglob("*.metta"))
        elif path.exists():
            yield path


def read_metta_evidence(paths: Iterable[str | Path]) -> Iterable[EvidenceFact]:
    for path in _input_paths(paths):
        current: dict | None = None
        order = 0

        def finish() -> EvidenceFact | None:
            if current is None:
                return None
            return EvidenceFact(
                relation=current["relation"],
                source=safe_symbol(current["source"]),
                target=safe_symbol(current["target"]),
                weight=current["weight"],
                surface_text=current["surface_text"],
                source_file=str(path),
                order=current["order"],
            )

        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                tokens = tokenize_atom(line)
                if not tokens:
                    continue
                relation = RELATION_ALIASES.get(tokens[0].lower())
                if relation and len(tokens) >= 3:
                    previous = finish()
                    if previous:
                        yield previous
                    current = {
                        "relation": relation,
                        "source": tokens[1],
                        "target": tokens[2],
                        "weight": 1.0,
                        "surface_text": "",
                        "order": order,
                    }
                    order += 1
                elif current is not None and tokens[0] == "weight":
                    try:
                        current["weight"] = float(tokens[-1])
                    except ValueError:
                        pass
                elif current is not None and tokens[0] == "surfaceText":
                    current["surface_text"] = tokens[-1].strip("'\"")

        previous = finish()
        if previous:
            yield previous


class EvidenceStore:
    """In-memory concept index suitable for focused or fixture-sized builds."""

    def __init__(self, facts: Iterable[EvidenceFact] = ()):
        self._by_source: dict[str, list[EvidenceFact]] = defaultdict(list)
        self._by_target: dict[str, list[EvidenceFact]] = defaultdict(list)
        for fact in facts:
            self.add(fact)

    @classmethod
    def from_paths(cls, paths: Iterable[str | Path]) -> "EvidenceStore":
        return cls(read_metta_evidence(paths))

    def add(self, fact: EvidenceFact) -> None:
        self._by_source[fact.source].append(fact)
        self._by_target[fact.target].append(fact)

    def for_concept(
        self,
        concept: str,
        include_incoming: bool = True,
        limit: int | None = None,
    ) -> list[EvidenceFact]:
        concept = safe_symbol(concept)
        facts = list(self._by_source.get(concept, ()))
        if include_incoming:
            facts.extend(self._by_target.get(concept, ()))
        unique = {
            (
                fact.relation,
                fact.source,
                fact.target,
                fact.source_file,
                fact.order,
            ): fact
            for fact in facts
        }
        ranked = sorted(
            unique.values(),
            key=lambda item: (-item.weight, item.order, item.relation, item.target),
        )
        return ranked if limit is None else ranked[:limit]


class SQLiteEvidenceStore:
    """Disk-backed exact and neighborhood index for the full Concept Atomspace."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @classmethod
    def build(cls, path: str | Path, evidence_paths: Iterable[str | Path], rebuild: bool = False) -> "SQLiteEvidenceStore":
        store = cls(path)
        connection = sqlite3.connect(store.path)
        with connection:
            if rebuild:
                connection.execute("DROP TABLE IF EXISTS facts")
            connection.execute("CREATE TABLE IF NOT EXISTS facts (relation TEXT, source TEXT, target TEXT, weight REAL, surface_text TEXT, source_file TEXT, fact_order INTEGER, UNIQUE(relation, source, target, source_file, fact_order))")
            connection.execute("CREATE INDEX IF NOT EXISTS facts_source ON facts(source)")
            connection.execute("CREATE INDEX IF NOT EXISTS facts_target ON facts(target)")
            batch = []
            for fact in read_metta_evidence(evidence_paths):
                batch.append((fact.relation, fact.source, fact.target, fact.weight, fact.surface_text, fact.source_file, fact.order))
                if len(batch) >= 5000:
                    connection.executemany("INSERT OR IGNORE INTO facts VALUES (?,?,?,?,?,?,?)", batch)
                    batch.clear()
            if batch:
                connection.executemany("INSERT OR IGNORE INTO facts VALUES (?,?,?,?,?,?,?)", batch)
        connection.close()
        return store

    def for_concept(self, concept: str, include_incoming: bool = True, limit: int | None = None) -> list[EvidenceFact]:
        concept = safe_symbol(concept)
        clauses = "source = ? OR target = ?" if include_incoming else "source = ?"
        parameters: list[object] = [concept, concept] if include_incoming else [concept]
        sql = f"SELECT relation,source,target,weight,surface_text,source_file,fact_order FROM facts WHERE {clauses} ORDER BY weight DESC, fact_order"
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(limit)
        connection = sqlite3.connect(self.path)
        rows = connection.execute(sql, parameters).fetchall()
        connection.close()
        return [EvidenceFact(*row) for row in rows]
