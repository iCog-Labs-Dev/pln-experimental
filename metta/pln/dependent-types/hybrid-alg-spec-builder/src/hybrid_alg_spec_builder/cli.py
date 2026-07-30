"""Command-line interface for the standalone hybrid builder."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .cache import SpecificationCache
from .embeddings import HashEmbeddingProvider, OpenAIEmbeddingProvider, SchemaRetriever
from .evidence import EvidenceStore, SQLiteEvidenceStore
from .llm import DEFAULT_OPENAI_MODEL, NullLLM, OpenAILLM
from .ontology import OntologyRegistry
from .orchestrator import HybridAlgebraicSpecBuilder
from .prototypes import DEFAULT_PROTOTYPES
from .serializers import to_metta, to_readable


def _llm_from_args(args):
    if args.llm_mode == "off":
        return NullLLM()
    api_key = os.environ.get(args.llm_api_key_env, "")
    if not api_key:
        raise SystemExit(
            f"Environment variable {args.llm_api_key_env} is required for LLM use"
        )
    return OpenAILLM(
        api_key,
        args.llm_model,
        timeout=args.llm_timeout,
        base_url=args.openai_base_url,
        trace=not args.no_llm_trace,
    )


def build_command(args) -> int:
    if args.evidence_index:
        evidence = SQLiteEvidenceStore(args.evidence_index)
    else:
        evidence = EvidenceStore.from_paths(args.evidence)
    ontology = OntologyRegistry()
    api_key = os.environ.get(args.llm_api_key_env, "")
    embedding_provider = OpenAIEmbeddingProvider(api_key, args.embedding_model, base_url=args.openai_base_url) if api_key and args.llm_mode != "off" and not args.offline_embeddings else HashEmbeddingProvider(args.embedding_dimensions)
    retriever = SchemaRetriever(
        ontology,
        embedding_provider,
        DEFAULT_PROTOTYPES,
    )
    llm = _llm_from_args(args)
    cache = SpecificationCache(args.cache) if args.cache else None
    builder = HybridAlgebraicSpecBuilder(
        evidence,
        ontology=ontology,
        retriever=retriever,
        llm=llm,
        cache=cache,
        llm_mode=args.llm_mode,
        evidence_limit=args.evidence_limit,
        retrieval_top_k=args.top_k,
        include_incoming_evidence=args.include_incoming_evidence,
    )
    result = builder.build(args.concept, args.perspective, args.context)

    if args.format == "json":
        output = result.specification.to_json()
    elif args.format == "metta":
        output = to_metta(result.specification)
    else:
        output = to_readable(result.specification)
    if args.output:
        Path(args.output).write_text(output + ("" if output.endswith("\n") else "\n"))
    else:
        print(output)

    if args.verbose:
        print(
            f"valid={result.valid} cache_hit={result.cache_hit} "
            f"used_llm={result.used_llm}",
            file=sys.stderr,
        )
        for name, score in result.retrieved_schemas:
            print(f"retrieved {name}: {score:.4f}", file=sys.stderr)
        for issue in result.issues:
            print(
                f"{issue.severity} {issue.code}: {issue.detail}",
                file=sys.stderr,
            )
    return 0 if result.valid else 2


def index_command(args) -> int:
    SQLiteEvidenceStore.build(args.output, args.evidence, rebuild=args.rebuild)
    print(args.output)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    subparsers = root.add_subparsers(dest="command", required=True)
    index = subparsers.add_parser("index-evidence", help="Stream Concept Atomspace shards into a queryable SQLite index")
    index.add_argument("--evidence", action="append", required=True)
    index.add_argument("--output", required=True)
    index.add_argument("--rebuild", action="store_true")
    index.set_defaults(handler=index_command)
    build = subparsers.add_parser("build")
    build.add_argument("--concept", required=True)
    build.add_argument("--perspective", required=True)
    source = build.add_mutually_exclusive_group(required=True)
    source.add_argument("--evidence", action="append")
    source.add_argument("--evidence-index")
    build.add_argument("--context", default="", help="Sense/domain constraint, e.g. 'the mathematical limit of a real function'.")
    build.add_argument("--format", choices=("json", "readable", "metta"), default="readable")
    build.add_argument("--output")
    build.add_argument("--cache")
    build.add_argument("--top-k", type=int, default=5)
    build.add_argument("--evidence-limit", type=int, default=100)
    build.add_argument(
        "--include-incoming-evidence",
        action="store_true",
        help="Also use facts where the queried concept is the relation target.",
    )
    build.add_argument("--embedding-dimensions", type=int, default=384)
    build.add_argument("--llm-mode", choices=("off", "missing", "always"), default="always")
    build.add_argument("--llm-model", default=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
    build.add_argument("--openai-base-url", default=os.environ.get("OPENAI_BASE_URL"))
    build.add_argument("--llm-api-key-env", default="OPENAI_API_KEY")
    build.add_argument("--llm-timeout", type=float, default=45.0)
    build.add_argument("--no-llm-trace", action="store_true", help="Do not print OpenAI request and response payloads to stderr.")
    build.add_argument("--embedding-model", default="text-embedding-3-small")
    build.add_argument("--offline-embeddings", action="store_true")
    build.add_argument("--verbose", action="store_true")
    build.set_defaults(handler=build_command)
    return root


def main() -> None:
    args = parser().parse_args()
    raise SystemExit(args.handler(args))


if __name__ == "__main__":
    main()
