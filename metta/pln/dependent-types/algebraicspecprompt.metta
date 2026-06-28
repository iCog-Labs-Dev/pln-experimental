;; Prompt used by llm.metta for algebraic specification fallback.
;;
;; The fallback is intentionally part-scoped: the builder calls it only for
;; sections that are missing from the local perspective-tagged KB.

(= (algebraicspecprompt $concept (spec-request $perspective $part))
   ("You are generating fallback MeTTa for an algebraic specification builder. "
    "The exact concept token is " $concept ". "
    "The exact requested perspective token is " $perspective ". "
    "The requested section token is " $part ". "
    "Return exactly one outer MeTTa list, with no Markdown and no explanation. "
    "Do not return separate top-level atoms; every returned proof atom must be inside the single outer list. "
    "Do not wrap the outer list with colon; use ((: proof ...) (: proof ...)), never (: (: proof ...) (: proof ...)). "
    "Return at most five entries for the requested section. "
    "Every returned atom must use the exact concept token " $concept " and the exact perspective token " $perspective ". "
    "Never use spec-request as a perspective value. "
    "Use the class field for a narrower role or classification compatible with the requested perspective. "
    "The list must contain proof atoms shaped like (: proof (≞ (spec-sort concept perspective class sort) (stv strength confidence))), "
    "(: proof (≞ (spec-operation concept perspective class (operation name (-> InputSort OutputSort))) (stv strength confidence))), "
    "(: proof (≞ (spec-predicate concept perspective class predicate) (stv strength confidence))), "
    "or (: proof (≞ (spec-axiom concept perspective class axiom) (stv strength confidence))). "
    "For operations, the signature must always use the arrow form (-> InputSort ... OutputSort); never return a bare tuple such as (Person Person). "
    "Do not use variables beginning with $. Prefer concrete concept-specific predicates and axioms. "
    "Use conservative strength and confidence values around 0.35 to 0.55 because these are fallback guesses."))
