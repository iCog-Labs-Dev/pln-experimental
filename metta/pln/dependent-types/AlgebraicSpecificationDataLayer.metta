!(import! &self synthesizers)
!(import! &self llm)
!(import! &self AlgebraicSpecificationKB)

;; Data-layer algebraic specification builder.
;;
;; AlgebraicSpecificationKB.metta is generated from ConceptNet-style relation
;; files. The generator normalizes raw relations into perspective-tagged:
;;   has-sort
;;   has-operation
;;   operation-signature
;;   has-predicate
;;   has-axiom
;;
;; The synthesizer remains responsible for fetching only the features that
;; match the requested concept and perspective.

(= (spec-feature-formula (stv $featureS $featureC)
                         (stv $perspectiveS $perspectiveC))
    (stv (* $featureS $perspectiveS)
         (min $featureC $perspectiveC)))

(= (spec-operation-formula (stv $featureS $featureC)
                           (stv $signatureS $signatureC)
                           (stv $perspectiveS $perspectiveC))
    (stv (* $featureS (* $signatureS $perspectiveS))
         (min $featureC (min $signatureC $perspectiveC))))

(: spec-sort-rule (-> Atom))
(= (spec-sort-rule)
    (: SpecSort
        (-> (≞ (has-sort $edge $concept $perspective $sort) $featureTv)
            (≞ (classified-perspective $perspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-sort $concept $perspective $perspectiveClass $sort)
                (Method spec-feature-formula $featureTv $perspectiveTv)))))

(: spec-operation-rule (-> Atom))
(= (spec-operation-rule)
    (: SpecOperation
        (-> (≞ (has-operation $edge $concept $perspective $operation) $featureTv)
            (≞ (operation-signature $edge $signature) $signatureTv)
            (≞ (classified-perspective $perspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-operation $concept $perspective $perspectiveClass (operation $operation $signature))
                (Method spec-operation-formula $featureTv $signatureTv $perspectiveTv)))))

(: spec-predicate-rule (-> Atom))
(= (spec-predicate-rule)
    (: SpecPredicate
        (-> (≞ (has-predicate $edge $concept $perspective $predicate) $featureTv)
            (≞ (classified-perspective $perspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-predicate $concept $perspective $perspectiveClass $predicate)
                (Method spec-feature-formula $featureTv $perspectiveTv)))))

(: spec-axiom-rule (-> Atom))
(= (spec-axiom-rule)
    (: SpecAxiom
        (-> (≞ (has-axiom $edge $concept $perspective $axiom) $featureTv)
            (≞ (classified-perspective $perspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-axiom $concept $perspective $perspectiveClass $axiom)
                (Method spec-feature-formula $featureTv $perspectiveTv)))))

(: spec-rb (-> Atom))
(= (spec-rb)
    (superpose
        ((spec-sort-rule)
         (spec-operation-rule)
         (spec-predicate-rule)
         (spec-axiom-rule))))

(= (synthesize-spec-sorts $concept $perspective)
    (collapse
        (synthesize
            (: $proof (≞ (spec-sort $concept $perspective $perspectiveClass $sort) $tv))
            &self
            spec-rb
            (S Z))))

(= (synthesize-spec-operations $concept $perspective)
    (collapse
        (synthesize
            (: $proof (≞ (spec-operation $concept $perspective $perspectiveClass $operation) $tv))
            &self
            spec-rb
            (S Z))))

(= (synthesize-spec-predicates $concept $perspective)
    (collapse
        (synthesize
            (: $proof (≞ (spec-predicate $concept $perspective $perspectiveClass $predicate) $tv))
            &self
            spec-rb
            (S Z))))

(= (synthesize-spec-axioms $concept $perspective)
    (collapse
        (synthesize
            (: $proof (≞ (spec-axiom $concept $perspective $perspectiveClass $axiom) $tv))
            &self
            spec-rb
            (S Z))))

(= (build-algebraic-spec $concept $perspective)
    (let* (($sorts (synthesize-spec-sorts $concept $perspective))
           ($operations (synthesize-spec-operations $concept $perspective))
           ($predicates (synthesize-spec-predicates $concept $perspective))
           ($axioms (synthesize-spec-axioms $concept $perspective)))
        (Concept $concept
            (perspective $perspective)
            (spec
                (sorts $sorts)
                (ops $operations)
                (preds $predicates)
                (axioms $axioms)))))

(= (add-missing-part $items $part $result)
    (if (== $items ())
        (union-atom $result ($part))
        $result))

(= (missing-spec-parts $concept $perspective)
    (let* (($sorts (synthesize-spec-sorts $concept $perspective))
           ($operations (synthesize-spec-operations $concept $perspective))
           ($predicates (synthesize-spec-predicates $concept $perspective))
           ($axioms (synthesize-spec-axioms $concept $perspective)))
        (let* (($missing-sorts (add-missing-part $sorts sorts ()))
               ($missing-operations (add-missing-part $operations operations $missing-sorts))
               ($missing-predicates (add-missing-part $predicates predicates $missing-operations))
               ($missing-axioms (add-missing-part $axioms axioms $missing-predicates)))
            $missing-axioms)))

(= (llm-spec-part $concept $perspective $part)
    (sread
        (useGenAI
            algebraicspecprompt
            $concept
            (spec-request $perspective $part))))

(= (with-llm-fallback $items $concept $perspective $part)
    (if (== $items ())
        (llm-spec-part $concept $perspective $part)
        $items))

(= (build-algebraic-spec-with-fallback $concept $perspective)
    (let* (($sorts0 (synthesize-spec-sorts $concept $perspective))
           ($operations0 (synthesize-spec-operations $concept $perspective))
           ($predicates0 (synthesize-spec-predicates $concept $perspective))
           ($axioms0 (synthesize-spec-axioms $concept $perspective))
           ($sorts (with-llm-fallback $sorts0 $concept $perspective sorts))
           ($operations (with-llm-fallback $operations0 $concept $perspective operations))
           ($predicates (with-llm-fallback $predicates0 $concept $perspective predicates))
           ($axioms (with-llm-fallback $axioms0 $concept $perspective axioms)))
        (Concept $concept
            (perspective $perspective)
            (spec
                (sorts $sorts)
                (ops $operations)
                (preds $predicates)
                (axioms $axioms)))))

!(println! "===== Data-layer local spec: socialize under prerequisite-action =====")
!(build-algebraic-spec socialize prerequisite-action)

!(println! "===== Data-layer missing parts: computer under descriptive-property =====")
!(missing-spec-parts computer descriptive-property)

;; This is intentionally not executed during local tests because it calls Gemini
;; when any section is missing:
;; !(build-algebraic-spec-with-fallback computer descriptive-property)
