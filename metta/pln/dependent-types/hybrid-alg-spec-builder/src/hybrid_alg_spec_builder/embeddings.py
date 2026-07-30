"""Offline embeddings and schema/prototype retrieval."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from openai import OpenAI

from .ontology import OntologyRegistry


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """Deterministic dependency-free lexical embedding for offline operation.

    Word and character n-grams are hashed into a fixed vector. It is not meant
    to compete with a neural embedding model, but it provides real approximate
    retrieval and a stable fallback for tests and air-gapped deployments.
    """

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def _features(self, text: str) -> Iterable[str]:
        words = [
            token
            for token in re.split(r"[_\W]+", text.lower())
            if token
        ]
        yield from (f"w:{word}" for word in words)
        for left, right in zip(words, words[1:]):
            yield f"b:{left}_{right}"
        compact = "_".join(words)
        for size in (3, 4):
            for index in range(max(0, len(compact) - size + 1)):
                yield f"c:{compact[index:index + size]}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for feature in self._features(text):
                digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
                number = int.from_bytes(digest, "big")
                index = number % self.dimensions
                sign = 1.0 if number & 1 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class OpenAIEmbeddingProvider:
    """Neural semantic embeddings; callers may retain HashEmbeddingProvider offline."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        timeout: float = 45.0,
        base_url: str | None = None,
        client: Any | None = None,
    ):
        self.model = model
        self.client = client or OpenAI(
            api_key=api_key,
            timeout=timeout,
            base_url=base_url,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float",
        )
        return [
            item.embedding
            for item in sorted(response.data, key=lambda item: item.index)
        ]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


@dataclass(frozen=True)
class RetrievalHit:
    name: str
    score: float
    document: str
    kind: str = "schema"


class SchemaRetriever:
    def __init__(
        self,
        ontology: OntologyRegistry,
        embedding_provider: EmbeddingProvider | None = None,
        prototypes: dict[str, str] | None = None,
    ):
        self.ontology = ontology
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()
        self.prototypes = prototypes or {}

    def retrieve(
        self,
        concept: str,
        perspective: str,
        evidence_text: str,
        top_k: int = 4,
    ) -> list[RetrievalHit]:
        perspective = perspective.replace("-", "_")
        candidates: list[tuple[str, str, str]] = [
            (family.name, family.retrieval_document, "schema")
            for family in self.ontology.allowed_for(perspective)
        ]
        candidates.extend(
            (name, document, "prototype")
            for name, document in sorted(self.prototypes.items())
        )
        if not candidates:
            return []
        query = f"{concept} {perspective} {evidence_text}"
        vectors = self.embedding_provider.embed(
            [query] + [document for _name, document, _kind in candidates]
        )
        query_vector = vectors[0]
        hits = [
            RetrievalHit(name, cosine(query_vector, vector), document, kind)
            for (name, document, kind), vector in zip(candidates, vectors[1:])
        ]
        return sorted(hits, key=lambda item: (-item.score, item.name))[:top_k]
