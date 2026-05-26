!(import! &self synthesizers)

;; Prototype algebraic specification builder.
;;
;; A concept owns spec features directly:
;;   has-sort
;;   has-operation
;;   has-predicate
;;   has-axiom
;;
;; Each feature is tagged with a reusable, classified perspective. The
;; perspective is not a pair of concepts. It is a shared vocabulary item
;; that describes the context in which the feature is meaningful.

(: HouseConcept (≞ House (stv 0.96 0.92)))
(: ApartmentConcept (≞ Apartment (stv 0.94 0.9)))
(: MarketConcept (≞ Market (stv 0.92 0.88)))

;; Shared perspective vocabulary. These are the allowed perspective tags.
;; A real KB should keep this taxonomy centralized so concepts use the
;; same names consistently.
(: residential-shelter-perspective (≞ (classified-perspective residential-shelter functional-role) (stv 1.0 1.0)))
(: economic-valuation-perspective (≞ (classified-perspective economic-valuation economic-role) (stv 1.0 1.0)))
(: physical-structure-perspective (≞ (classified-perspective physical-structure structural-role) (stv 1.0 1.0)))
(: ui-interaction-perspective (≞ (classified-perspective ui-interaction interface-role) (stv 1.0 1.0)))

;; House features under the residential-shelter perspective.
(: house-sort-house (≞ (has-sort house-sort-house House residential-shelter House) (stv 1.0 0.94)))
(: house-sort-resident (≞ (has-sort house-sort-resident House residential-shelter Resident) (stv 0.94 0.88)))
(: house-sort-shelter-space (≞ (has-sort house-sort-shelter-space House residential-shelter ShelterSpace) (stv 0.96 0.9)))

(: house-op-house (≞ (has-operation house-op-house House residential-shelter (house : (-> ShelterSpace House))) (stv 0.95 0.9)))
(: house-op-resident (≞ (has-operation house-op-resident House residential-shelter (resident : (-> House Resident))) (stv 0.92 0.88)))
(: house-op-enter (≞ (has-operation house-op-enter House residential-shelter (enter : (-> Resident House House))) (stv 0.9 0.86)))

(: house-pred-provides-shelter (≞ (has-predicate house-pred-provides-shelter House residential-shelter (providesShelter House Resident)) (stv 0.97 0.9)))
(: house-pred-has-resident (≞ (has-predicate house-pred-has-resident House residential-shelter (hasResident House Resident)) (stv 0.94 0.88)))

(: house-axiom-resident-shelter (≞ (has-axiom house-axiom-resident-shelter House residential-shelter (=> (hasResident House Resident) (providesShelter House Resident))) (stv 0.93 0.86)))

;; Apartment uses the same residential-shelter perspective. This is the
;; intended consistency benefit of classified perspective tagging.
(: apartment-sort-apartment (≞ (has-sort apartment-sort-apartment Apartment residential-shelter Apartment) (stv 1.0 0.92)))
(: apartment-sort-resident (≞ (has-sort apartment-sort-resident Apartment residential-shelter Resident) (stv 0.93 0.88)))
(: apartment-sort-unit (≞ (has-sort apartment-sort-unit Apartment residential-shelter Unit) (stv 0.95 0.89)))

(: apartment-op-leaseholder (≞ (has-operation apartment-op-leaseholder Apartment residential-shelter (leaseholder : (-> Apartment Resident))) (stv 0.9 0.86)))
(: apartment-pred-provides-shelter (≞ (has-predicate apartment-pred-provides-shelter Apartment residential-shelter (providesShelter Apartment Resident)) (stv 0.95 0.89)))

;; House has a different algebraic specification under economic valuation.
(: house-market-sort-asset (≞ (has-sort house-market-sort-asset House economic-valuation Asset) (stv 0.94 0.86)))
(: house-market-sort-currency (≞ (has-sort house-market-sort-currency House economic-valuation Currency) (stv 0.9 0.84)))

(: house-market-op-price (≞ (has-operation house-market-op-price House economic-valuation (price : (-> House Currency))) (stv 0.91 0.84)))
(: house-market-op-list (≞ (has-operation house-market-op-list House economic-valuation (listForSale : (-> House Market Asset))) (stv 0.89 0.83)))

(: house-market-pred-value (≞ (has-predicate house-market-pred-value House economic-valuation (hasMarketValue House Currency)) (stv 0.9 0.84)))

(: house-market-axiom-price-value (≞ (has-axiom house-market-axiom-price-value House economic-valuation (=> (price House Currency) (hasMarketValue House Currency))) (stv 0.88 0.82)))

;; House has another separate spec under physical structure.
(: house-structure-sort-room (≞ (has-sort house-structure-sort-room House physical-structure Room) (stv 0.95 0.88)))
(: house-structure-sort-wall (≞ (has-sort house-structure-sort-wall House physical-structure Wall) (stv 0.94 0.87)))
(: house-structure-sort-roof (≞ (has-sort house-structure-sort-roof House physical-structure Roof) (stv 0.92 0.86)))

(: house-structure-op-room (≞ (has-operation house-structure-op-room House physical-structure (room : (-> House Room))) (stv 0.91 0.85)))
(: house-structure-op-attach-roof (≞ (has-operation house-structure-op-attach-roof House physical-structure (attachRoof : (-> House Roof House))) (stv 0.88 0.82)))

(: house-structure-pred-has-room (≞ (has-predicate house-structure-pred-has-room House physical-structure (hasRoom House Room)) (stv 0.92 0.86)))

(: house-structure-axiom-room-part (≞ (has-axiom house-structure-axiom-room-part House physical-structure (=> (hasRoom House Room) (partOf Room House))) (stv 0.9 0.83)))

;; Same operation label, but different perspective. It must not appear in
;; the residential-shelter spec unless that perspective is requested.
(: house-ui-op-enter (≞ (has-operation house-ui-op-enter House ui-interaction (enter : (-> Click HouseView))) (stv 0.7 0.55)))

(= (spec-feature-formula (stv $featureS $featureC)
                         (stv $perspectiveS $perspectiveC))
    (stv (* $featureS $perspectiveS)
         (min $featureC $perspectiveC)))

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
            (≞ (classified-perspective $perspective $perspectiveClass) $perspectiveTv)
            (≞ (spec-operation $concept $perspective $perspectiveClass $operation)
                (Method spec-feature-formula $featureTv $perspectiveTv)))))

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

!(println! "===== Build House spec under residential-shelter =====")
!(build-algebraic-spec House residential-shelter)

!(println! "===== Build House spec under economic-valuation =====")
!(build-algebraic-spec House economic-valuation)

!(println! "===== Build House spec under physical-structure =====")
!(build-algebraic-spec House physical-structure)

!(println! "===== Build Apartment spec under residential-shelter =====")
!(build-algebraic-spec Apartment residential-shelter)
