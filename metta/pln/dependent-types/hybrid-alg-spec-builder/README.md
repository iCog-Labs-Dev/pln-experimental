# Hybrid algebraic specification builder

This standalone builder generates algebraic specifications on demand. It does
not attempt to enumerate every concept or every useful word in a static KB.

It combines:

1. ConceptNet-style evidence;
2. a cross-domain ontology of formal primitives and schema families;
3. embedding-based schema and prototype retrieval;
4. an optional constrained LLM semantic-frame proposer;
5. deterministic algebraic compilation;
6. logical and structural validation;
7. provenance-sensitive confidence;
8. a SQLite cache of validated generated specifications.

It is independent of the generator now located at
`../v-predicate-extraction-pipeline/python/generation/gen_algebraic_spec_kb.py`.

## Knowledge layers

| Layer | Implementation | Purpose |
|---|---|---|
| Evidence KB | `SQLiteEvidenceStore` | Streaming, disk-backed full Concept Atomspace index |
| Ontology KB | `OntologyRegistry` | Canonical roles and schema families |
| Prototype Spec KB | `DEFAULT_PROTOTYPES` | Reviewed examples for analogical retrieval |
| Generated Spec Cache | `SpecificationCache` | Validated query-specific specifications |

The system stores general semantic primitives and schema families rather than
attempting to store all possible vocabulary.

## Safety boundary

The LLM never writes MeTTa directly. The Responses API is constrained by a
strict JSON schema and proposes typed formal IR containing:

- ontology-approved schema families;
- arbitrary many-sorted operation signatures;
- non-transformational relations;
- typed equational axioms with explicit operation references;
- evidence or analogy references;
- bounded confidence.

The deterministic compiler produces the formal specification. A result is only
cached if it passes:

- sort closure;
- operation signature closure;
- axiom symbol closure;
- operation/predicate semantic separation;
- schema dependency checks;
- perspective/schema compatibility checks;
- confidence bounds.

If LLM generation fails validation, the builder discards it and returns the
smaller evidence-grounded fallback. It does not cache invalid output.

## Production setup

Install the package and its official `openai` SDK dependency:

```bash
python3 -m pip install -e metta/pln/dependent-types/hybrid-alg-spec-builder
```

Index the complete checked-in Concept Atomspace once. The indexer streams the
shards and does not hold the corpus in RAM:

```bash
PYTHONPATH=metta/pln/dependent-types/hybrid-alg-spec-builder/src \
python3 -m hybrid_alg_spec_builder.cli index-evidence \
  --evidence metta/pln/dependent-types/v-predicate-extraction-pipeline/kb/evidence/concept-atomspace \
  --output /path/to/concept-atomspace.sqlite3
```

Then build with neural retrieval and strict structured generation:

```bash
export OPENAI_API_KEY='...'
PYTHONPATH=metta/pln/dependent-types/hybrid-alg-spec-builder/src \
python3 -m hybrid_alg_spec_builder.cli build \
  --concept limit \
  --perspective functional_use \
  --context 'the mathematical limit of a real-valued function' \
  --evidence-index /path/to/concept-atomspace.sqlite3 \
  --format readable
```

`--context` is important for polysemous concepts. It is included in retrieval,
generation, and the cache digest, so mathematical `limit` and a legal speed
limit cannot collide.

## Offline usage

The package still requires the official SDK to be installed, but
`--llm-mode off --offline-embeddings` performs no API calls:

```bash
PYTHONPATH=metta/pln/dependent-types/hybrid-alg-spec-builder/src \
python3 -m hybrid_alg_spec_builder.cli build \
  --concept knife \
  --perspective functional_use \
  --evidence metta/pln/dependent-types/hybrid-alg-spec-builder/tests/fixtures/concepts.metta \
  --llm-mode off \
  --format readable
```

Available output formats are `readable`, `json`, and `metta`.

Use a persistent generated-spec cache with:

```bash
--cache /path/to/generated-specs.sqlite3
```

The cache key includes the concept, perspective, ontology version, evidence
digest, and LLM model ID.

Only outbound evidence is used by default. Pass `--include-incoming-evidence`
when inverse or target-side relations are deliberately needed; keeping it
opt-in prevents facts such as `CapableOf(other, query)` from contaminating the
queried concept's capability model.

## Structured OpenAI stage

The production adapter uses the official OpenAI Python SDK, the Responses API,
and Structured Outputs. `gpt-5.4` is the default generation model. The model,
SDK base URL, and embedding model remain configurable:

```bash
export OPENAI_API_KEY='...'

PYTHONPATH=metta/pln/dependent-types/hybrid-alg-spec-builder/src \
python3 -m hybrid_alg_spec_builder.cli build \
  --concept house \
  --perspective functional_use \
  --context 'a residential building used for habitation and shelter' \
  --evidence-index /path/to/concept-atomspace.sqlite3 \
  --llm-mode always \
  --format json
```

LLM modes:

- `off`: never call an LLM;
- `missing`: call it when grounded capabilities or schema coverage are sparse;
- `always`: request enrichment for every query.

`always` is the production default. Use `--llm-mode off --offline-embeddings`
for deterministic air-gapped operation.

Build commands print the exact LLM instructions, user payload, selected model,
and raw structured response to stderr. This also traces a validation-repair
request when one occurs. Pass `--no-llm-trace` to suppress the trace for
automation or when evidence may contain sensitive text.

Override the generation model with `--llm-model` or `OPENAI_MODEL`; override
the SDK base URL, when required, with `--openai-base-url` or
`OPENAI_BASE_URL`.

## Embeddings

`OpenAIEmbeddingProvider` is the production default when an API key is present.
It retrieves cross-domain ontology and prototype candidates. The
`HashEmbeddingProvider` remains dependency-free and deterministic. It
uses hashed word, word-bigram, and character n-gram features. It supports
offline operation, lexical variation, regression tests, and air-gapped
deployments.

`EmbeddingProvider` is a protocol. A neural embedding provider can be injected
without changing the retriever or builder. High-confidence neural retrieval
may bridge lexical gaps; weaker local matches require direct keyword support
before activating a schema family.

Embeddings retrieve candidates. They do not establish truth.

## Cross-domain ontology

The initial ontology includes:

- mathematical structures and analysis/limits
- spatial containers and buildings
- information transformation and measurement
- social institutions and biological processes

- functional interface
- edge application
- transport
- containment
- computation
- communication
- perception
- material transformation
- agent action
- structural composition
- taxonomic interface
- descriptive observation
- risk management
- state lifecycle
- prerequisite action
- spatial state
- value assessment

Each family is finite and reusable. For example, `edge-application` introduces
formal roles such as `motion`, `force`, `use_configuration`, and
`use_outcome`. These words do not need to occur in ConceptNet.

## Tests

```bash
PYTHONPATH=metta/pln/dependent-types/hybrid-alg-spec-builder/src \
python3 -B -m unittest discover \
  -s metta/pln/dependent-types/hybrid-alg-spec-builder/tests \
  -v
```

The suite covers evidence parsing, the disk index, offline retrieval, rich knife compilation,
operation/predicate separation, constrained LLM gap filling, forbidden schema
rejection, provenance confidence ceilings, SQLite cache round trips,
serializers, stratified validity, and explicit house/mathematical-limit
distinctness with rejection of the knife motion/force template.

## Evaluation

```bash
python3 -B metta/pln/dependent-types/hybrid-alg-spec-builder/evaluate.py
```

Use `--json` for a machine-readable report. The evaluator measures validation
errors, operation/predicate overlaps, section sizes, provenance coverage, and
per-query schema selection.

## Package installation

```bash
python3 -m pip install -e \
  metta/pln/dependent-types/hybrid-alg-spec-builder
```

This exposes the `hybrid-alg-spec` command.
