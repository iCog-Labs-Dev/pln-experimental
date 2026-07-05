!(import! &self ../../../../PeTTa/lib/lib_import)
!(import! &self synthesizers)
!(import! &self llm)
!(static-import! &algkb AlgebraicSpecificationKB)

; !(py-eval "setattr(__import__('builtins'),'normalize_metta_list_text',__import__('importlib').import_module('algebraic_spec_fallback').normalize_metta_list_text) or 0")

;; Data-layer algebraic specification builder.
;;
;; AlgebraicSpecificationKB.metta is generated from ConceptNet-style relation
;; files. The generator normalizes raw relations into perspective-tagged:
;;   has_sort
;;   has_operation
;;   operation_signature
;;   has_predicate
;;   has_axiom
;;
;; The synthesizer remains responsible for fetching only the features that
;; match the requested concept and perspective. Perspective matching is
;; generated in AlgebraicSpecificationKB.metta and loaded into &algkb, so a broad request such as
;; descriptive-property can collect narrow perspectives such as
;; physical-attribute, safety-risk, and information-computational.

(= (max-spec-items) (S (S (S (S (S Z))))))

(= (take-spec-items Z $items) ())
(= (take-spec-items (S $n) $items)
    (if (== $items ())
        ()
        (cons-atom
            (car-atom $items)
            (take-spec-items $n (cdr-atom $items)))))

(= (limit-spec-items $items)
    (take-spec-items (max-spec-items) $items))


(= (kb-perspective-name descriptive-property) descriptive_property)
(= (kb-perspective-name taxonomic-classification) taxonomic_classification)
(= (kb-perspective-name prerequisite-action) prerequisite_action)
(= (kb-perspective-name event-composition) event_composition)
(= (kb-perspective-name taxonomic-kind) taxonomic_kind)
(= (kb-perspective-name artifact-kind) artifact_kind)
(= (kb-perspective-name role-kind) role_kind)
(= (kb-perspective-name structural-composition) structural_composition)
(= (kb-perspective-name physical-attribute) physical_attribute)
(= (kb-perspective-name functional-use) functional_use)
(= (kb-perspective-name behavioral-process) behavioral_process)
(= (kb-perspective-name causal-prerequisite) causal_prerequisite)
(= (kb-perspective-name spatial-context) spatial_context)
(= (kb-perspective-name temporal-context) temporal_context)
(= (kb-perspective-name quantitative-comparative) quantitative_comparative)
(= (kb-perspective-name social-normative) social_normative)
(= (kb-perspective-name economic-ownership) economic_ownership)
(= (kb-perspective-name information-computational) information_computational)
(= (kb-perspective-name safety-risk) safety_risk)
(= (kb-perspective-name state-lifecycle) state_lifecycle)
(= (kb-perspective-name descriptive_property) descriptive_property)
(= (kb-perspective-name taxonomic_classification) taxonomic_classification)
(= (kb-perspective-name prerequisite_action) prerequisite_action)
(= (kb-perspective-name event_composition) event_composition)
(= (kb-perspective-name taxonomic_kind) taxonomic_kind)
(= (kb-perspective-name artifact_kind) artifact_kind)
(= (kb-perspective-name role_kind) role_kind)
(= (kb-perspective-name structural_composition) structural_composition)
(= (kb-perspective-name physical_attribute) physical_attribute)
(= (kb-perspective-name functional_use) functional_use)
(= (kb-perspective-name behavioral_process) behavioral_process)
(= (kb-perspective-name causal_prerequisite) causal_prerequisite)
(= (kb-perspective-name spatial_context) spatial_context)
(= (kb-perspective-name temporal_context) temporal_context)
(= (kb-perspective-name quantitative_comparative) quantitative_comparative)
(= (kb-perspective-name social_normative) social_normative)
(= (kb-perspective-name economic_ownership) economic_ownership)
(= (kb-perspective-name information_computational) information_computational)
(= (kb-perspective-name safety_risk) safety_risk)
(= (kb-perspective-name state_lifecycle) state_lifecycle)

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
        (-> (≞ (has_sort $edge $concept $featurePerspective $sort) $featureTv)
            (≞ (perspective_match $requestedPerspective $featurePerspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-sort $concept $requestedPerspective $perspectiveClass $sort)
                (Method spec-feature-formula $featureTv $perspectiveTv)))))

(: spec-operation-rule (-> Atom))
(= (spec-operation-rule)
    (: SpecOperation
        (-> (≞ (has_operation $edge $concept $featurePerspective $operation) $featureTv)
            (≞ (operation_signature $edge $signature) $signatureTv)
            (≞ (perspective_match $requestedPerspective $featurePerspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-operation $concept $requestedPerspective $perspectiveClass (operation $operation $signature))
                (Method spec-operation-formula $featureTv $signatureTv $perspectiveTv)))))

(: spec-predicate-rule (-> Atom))
(= (spec-predicate-rule)
    (: SpecPredicate
        (-> (≞ (has_predicate $edge $concept $featurePerspective $predicate) $featureTv)
            (≞ (perspective_match $requestedPerspective $featurePerspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-predicate $concept $requestedPerspective $perspectiveClass $predicate)
                (Method spec-feature-formula $featureTv $perspectiveTv)))))

(: spec-axiom-rule (-> Atom))
(= (spec-axiom-rule)
    (: SpecAxiom
        (-> (≞ (has_axiom $edge $concept $featurePerspective $axiom) $featureTv)
            (≞ (perspective_match $requestedPerspective $featurePerspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-axiom $concept $requestedPerspective $perspectiveClass $axiom)
                (Method spec-feature-formula $featureTv $perspectiveTv)))))

(: spec-rb (-> Atom))
(= (spec-rb)
    (superpose
        ((spec-sort-rule)
         (spec-operation-rule)
         (spec-predicate-rule)
         (spec-axiom-rule))))

(= (synthesize-spec-sorts $concept $perspective)
    (let $kbPerspective (kb-perspective-name $perspective)
        (limit-spec-items
            (collapse
                (synthesize
                    (: $proof (≞ (spec-sort $concept $kbPerspective $perspectiveClass $sort) $tv))
                    &algkb
                    spec-rb
                    (S Z))))))

(= (synthesize-spec-operations $concept $perspective)
    (let $kbPerspective (kb-perspective-name $perspective)
        (limit-spec-items
            (collapse
                (synthesize
                    (: $proof (≞ (spec-operation $concept $kbPerspective $perspectiveClass $operation) $tv))
                    &algkb
                    spec-rb
                    (S Z))))))

(= (synthesize-spec-predicates $concept $perspective)
    (let $kbPerspective (kb-perspective-name $perspective)
        (limit-spec-items
            (collapse
                (synthesize
                    (: $proof (≞ (spec-predicate $concept $kbPerspective $perspectiveClass $predicate) $tv))
                    &algkb
                    spec-rb
                    (S Z))))))

(= (synthesize-spec-axioms $concept $perspective)
    (let $kbPerspective (kb-perspective-name $perspective)
        (limit-spec-items
            (collapse
                (synthesize
                    (: $proof (≞ (spec-axiom $concept $kbPerspective $perspectiveClass $axiom) $tv))
                    &algkb
                    spec-rb
                    (S Z))))))

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
    (let $text
        (useGenAI
            algebraicspecprompt
            $concept
            (spec-request $perspective $part))
        (sread
            (py-call (builtins.normalize_metta_list_text $text $concept $perspective $part)))))

(= (with-llm-fallback $items $concept $perspective $part)
    (limit-spec-items
        (if (== $items ())
            (llm-spec-part $concept $perspective $part)
            $items)))

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

; !(println! "===== Data-layer local spec: socialize under behavioral-process =====")
; !(build-algebraic-spec socialize behavioral-process)

!(println! "===== Data-layer local spec: socialize under prerequisite-action =====")
!(build-algebraic-spec socialize prerequisite-action)

; !(println! "===== Data-layer local spec: start_fire under behavioral-process =====")
; !(build-algebraic-spec start_fire behavioral-process)

; !(println! "===== Data-layer local spec: start_fire under prerequisite-action =====")
; !(build-algebraic-spec start_fire prerequisite-action)

; !(println! "===== Data-layer local spec: computer under taxonomic-classification =====")
; !(build-algebraic-spec computer taxonomic-classification)

; !(println! "===== Data-layer local spec: abstract_computer_file under information-computational =====")
; !(build-algebraic-spec abstract_computer_file information-computational)

; !(println! "===== Data-layer local spec: car under functional-use =====")
; !(build-algebraic-spec car functional-use)

; !(println! "===== Data-layer local spec: car under economic-ownership =====")
; !(build-algebraic-spec car economic-ownership)

; !(println! "===== Data-layer local spec: computer under descriptive-property with fallback =====")
; !(build-algebraic-spec-with-fallback computer descriptive-property)

; !(println! "===== Data-layer missing parts: computer under descriptive-property =====")
; !(missing-spec-parts computer descriptive-property)

;; This is intentionally not executed during local tests because it calls Gemini
;; when any section is missing:
;; !(build-algebraic-spec-with-fallback unknown_concept descriptive-property)
