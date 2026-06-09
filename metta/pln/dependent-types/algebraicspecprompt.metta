;; Prompt used by llm.metta for algebraic specification fallback.
;;
;; The fallback is intentionally part-scoped: the builder calls it only for
;; sections that are missing from the local perspective-tagged KB.

(= (algebraicspecprompt $concept $request)
   ("You are generating fallback MeTTa for an algebraic specification builder. "
    "The request is " $request ". "
    "Return only one MeTTa list, with no Markdown and no explanation. "
    "The list must contain proof atoms shaped like (: proof (≞ (spec-sort concept perspective class sort) (stv strength confidence))), "
    "(: proof (≞ (spec-operation concept perspective class (operation name signature)) (stv strength confidence))), "
    "(: proof (≞ (spec-predicate concept perspective class predicate) (stv strength confidence))), "
    "or (: proof (≞ (spec-axiom concept perspective class axiom) (stv strength confidence))). "
    "Use the exact concept " $concept ". "
    "Use conservative confidence values around 0.35 to 0.55 because these are fallback guesses."))
