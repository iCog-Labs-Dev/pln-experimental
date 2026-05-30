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
(: OccupiedShelterWorldConcept (≞ OccupiedShelterWorld (stv 0.9 0.86)))
(: ProtectedShelterWorldConcept (≞ ProtectedShelterWorld (stv 0.89 0.84)))
(: TemporaryShelterWorldConcept (≞ TemporaryShelterWorld (stv 0.87 0.82)))
(: LeasedResidenceWorldConcept (≞ LeasedResidenceWorld (stv 0.88 0.83)))

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

(: house-op-house (≞ (has-operation house-op-house House residential-shelter house) (stv 0.95 0.9)))
(: house-op-house-signature (≞ (operation-signature house-op-house (-> ShelterSpace House)) (stv 1.0 0.95)))
(: house-op-resident (≞ (has-operation house-op-resident House residential-shelter resident) (stv 0.92 0.88)))
(: house-op-resident-signature (≞ (operation-signature house-op-resident (-> House Resident)) (stv 1.0 0.94)))
(: house-op-enter (≞ (has-operation house-op-enter House residential-shelter enter) (stv 0.9 0.86)))
(: house-op-enter-signature (≞ (operation-signature house-op-enter (-> Resident HouseState HouseState)) (stv 1.0 0.92)))

(: house-pred-provides-shelter (≞ (has-predicate house-pred-provides-shelter House residential-shelter (providesShelter House Resident)) (stv 0.97 0.9)))
(: house-pred-has-resident (≞ (has-predicate house-pred-has-resident House residential-shelter (hasResident House Resident)) (stv 0.94 0.88)))

(: house-axiom-resident-shelter (≞ (has-axiom house-axiom-resident-shelter House residential-shelter (=> (hasResident House Resident) (providesShelter House Resident))) (stv 0.93 0.86)))

;; Perspective-relevant properties used by the V-predicate builder.
(: house-property-provides-shelter (≞ (has-property house-property-provides-shelter House residential-shelter providesShelter) (stv 0.96 0.88)))
(: house-property-provides-shelter-degree (≞ (property-expressiveness house-property-provides-shelter 0.91) (stv 1.0 0.9)))
(: house-property-has-resident (≞ (has-property house-property-has-resident House residential-shelter hasResident) (stv 0.93 0.86)))
(: house-property-has-resident-degree (≞ (property-expressiveness house-property-has-resident 0.84) (stv 1.0 0.9)))
(: house-property-weather-resistant (≞ (has-property house-property-weather-resistant House residential-shelter weatherResistant) (stv 0.7 0.7)))
(: house-property-weather-resistant-degree (≞ (property-expressiveness house-property-weather-resistant 0.37) (stv 1.0 0.9)))

;; Property-to-possible-world mapping. The world names are later turned
;; into WorldSpec placeholders after building their algebraic specs.
(: provides-shelter-world-occupied (≞ (property-possible-world provides-shelter-world-occupied providesShelter residential-shelter OccupiedShelterWorld) (stv 0.94 0.86)))
(: provides-shelter-world-protected (≞ (property-possible-world provides-shelter-world-protected providesShelter residential-shelter ProtectedShelterWorld) (stv 0.9 0.83)))
(: provides-shelter-world-temporary (≞ (property-possible-world provides-shelter-world-temporary providesShelter residential-shelter TemporaryShelterWorld) (stv 0.82 0.78)))
(: has-resident-world-occupied (≞ (property-possible-world has-resident-world-occupied hasResident residential-shelter OccupiedShelterWorld) (stv 0.93 0.84)))
(: has-resident-world-leased (≞ (property-possible-world has-resident-world-leased hasResident residential-shelter LeasedResidenceWorld) (stv 0.86 0.8)))

;; Apartment uses the same residential-shelter perspective. This is the
;; intended consistency benefit of classified perspective tagging.
(: apartment-sort-apartment (≞ (has-sort apartment-sort-apartment Apartment residential-shelter Apartment) (stv 1.0 0.92)))
(: apartment-sort-resident (≞ (has-sort apartment-sort-resident Apartment residential-shelter Resident) (stv 0.93 0.88)))
(: apartment-sort-unit (≞ (has-sort apartment-sort-unit Apartment residential-shelter Unit) (stv 0.95 0.89)))

(: apartment-op-leaseholder (≞ (has-operation apartment-op-leaseholder Apartment residential-shelter leaseholder) (stv 0.9 0.86)))
(: apartment-op-leaseholder-signature (≞ (operation-signature apartment-op-leaseholder (-> Apartment Resident)) (stv 1.0 0.92)))
(: apartment-pred-provides-shelter (≞ (has-predicate apartment-pred-provides-shelter Apartment residential-shelter (providesShelter Apartment Resident)) (stv 0.95 0.89)))

;; House has a different algebraic specification under economic valuation.
(: house-market-sort-asset (≞ (has-sort house-market-sort-asset House economic-valuation Asset) (stv 0.94 0.86)))
(: house-market-sort-currency (≞ (has-sort house-market-sort-currency House economic-valuation Currency) (stv 0.9 0.84)))

(: house-market-op-price (≞ (has-operation house-market-op-price House economic-valuation price) (stv 0.91 0.84)))
(: house-market-op-price-signature (≞ (operation-signature house-market-op-price (-> House Currency)) (stv 1.0 0.92)))
(: house-market-op-list (≞ (has-operation house-market-op-list House economic-valuation listForSale) (stv 0.89 0.83)))
(: house-market-op-list-signature (≞ (operation-signature house-market-op-list (-> House Market Asset)) (stv 1.0 0.91)))

(: house-market-pred-value (≞ (has-predicate house-market-pred-value House economic-valuation (hasMarketValue House Currency)) (stv 0.9 0.84)))

(: house-market-axiom-price-value (≞ (has-axiom house-market-axiom-price-value House economic-valuation (=> (price House Currency) (hasMarketValue House Currency))) (stv 0.88 0.82)))

(: house-market-property-value (≞ (has-property house-market-property-value House economic-valuation hasMarketValue) (stv 0.9 0.84)))
(: house-market-property-value-degree (≞ (property-expressiveness house-market-property-value 0.76) (stv 1.0 0.88)))

;; House has another separate spec under physical structure.
(: house-structure-sort-room (≞ (has-sort house-structure-sort-room House physical-structure Room) (stv 0.95 0.88)))
(: house-structure-sort-wall (≞ (has-sort house-structure-sort-wall House physical-structure Wall) (stv 0.94 0.87)))
(: house-structure-sort-roof (≞ (has-sort house-structure-sort-roof House physical-structure Roof) (stv 0.92 0.86)))

(: house-structure-op-room (≞ (has-operation house-structure-op-room House physical-structure room) (stv 0.91 0.85)))
(: house-structure-op-room-signature (≞ (operation-signature house-structure-op-room (-> House Room)) (stv 1.0 0.92)))
(: house-structure-op-attach-roof (≞ (has-operation house-structure-op-attach-roof House physical-structure attachRoof) (stv 0.88 0.82)))
(: house-structure-op-attach-roof-signature (≞ (operation-signature house-structure-op-attach-roof (-> House Roof House)) (stv 1.0 0.9)))

(: house-structure-pred-has-room (≞ (has-predicate house-structure-pred-has-room House physical-structure (hasRoom House Room)) (stv 0.92 0.86)))

(: house-structure-axiom-room-part (≞ (has-axiom house-structure-axiom-room-part House physical-structure (=> (hasRoom House Room) (partOf Room House))) (stv 0.9 0.83)))

;; Same operation label, but different perspective. It must not appear in
;; the residential-shelter spec unless that perspective is requested.
(: house-ui-op-enter (≞ (has-operation house-ui-op-enter House ui-interaction enter) (stv 0.7 0.55)))
(: house-ui-op-enter-signature (≞ (operation-signature house-ui-op-enter (-> Click HouseView)) (stv 1.0 0.8)))

;; Possible-world algebraic specs. These are ordinary concepts with
;; ordinary perspective-tagged spec features, so the same builder works.
(: occupied-world-sort-state (≞ (has-sort occupied-world-sort-state OccupiedShelterWorld residential-shelter OccupancyState) (stv 0.92 0.86)))
(: occupied-world-sort-resident (≞ (has-sort occupied-world-sort-resident OccupiedShelterWorld residential-shelter Resident) (stv 0.9 0.84)))
(: occupied-world-op-occupy (≞ (has-operation occupied-world-op-occupy OccupiedShelterWorld residential-shelter occupy) (stv 0.88 0.82)))
(: occupied-world-op-occupy-signature (≞ (operation-signature occupied-world-op-occupy (-> Resident ShelterSpace OccupancyState)) (stv 1.0 0.9)))
(: occupied-world-pred-occupied (≞ (has-predicate occupied-world-pred-occupied OccupiedShelterWorld residential-shelter (occupied ShelterSpace Resident)) (stv 0.9 0.84)))
(: occupied-world-axiom-occupied (≞ (has-axiom occupied-world-axiom-occupied OccupiedShelterWorld residential-shelter (=> (occupied ShelterSpace Resident) (hasResident House Resident))) (stv 0.86 0.8)))

(: protected-world-sort-hazard (≞ (has-sort protected-world-sort-hazard ProtectedShelterWorld residential-shelter WeatherHazard) (stv 0.9 0.83)))
(: protected-world-sort-barrier (≞ (has-sort protected-world-sort-barrier ProtectedShelterWorld residential-shelter Barrier) (stv 0.88 0.82)))
(: protected-world-op-protect (≞ (has-operation protected-world-op-protect ProtectedShelterWorld residential-shelter protectFrom) (stv 0.86 0.8)))
(: protected-world-op-protect-signature (≞ (operation-signature protected-world-op-protect (-> ShelterSpace WeatherHazard Barrier)) (stv 1.0 0.88)))
(: protected-world-pred-protected (≞ (has-predicate protected-world-pred-protected ProtectedShelterWorld residential-shelter (protectedFrom ShelterSpace WeatherHazard)) (stv 0.88 0.82)))

(: temporary-world-sort-duration (≞ (has-sort temporary-world-sort-duration TemporaryShelterWorld residential-shelter Duration) (stv 0.86 0.8)))
(: temporary-world-op-expire (≞ (has-operation temporary-world-op-expire TemporaryShelterWorld residential-shelter expireShelter) (stv 0.82 0.78)))
(: temporary-world-op-expire-signature (≞ (operation-signature temporary-world-op-expire (-> ShelterSpace Duration ShelterSpace)) (stv 1.0 0.86)))
(: temporary-world-pred-temporary (≞ (has-predicate temporary-world-pred-temporary TemporaryShelterWorld residential-shelter (temporaryShelter ShelterSpace Duration)) (stv 0.84 0.79)))

(: leased-world-sort-lease (≞ (has-sort leased-world-sort-lease LeasedResidenceWorld residential-shelter LeaseAgreement) (stv 0.88 0.82)))
(: leased-world-op-lease (≞ (has-operation leased-world-op-lease LeasedResidenceWorld residential-shelter leaseTo) (stv 0.84 0.8)))
(: leased-world-op-lease-signature (≞ (operation-signature leased-world-op-lease (-> ShelterSpace Resident LeaseAgreement)) (stv 1.0 0.86)))
(: leased-world-pred-leaseholder (≞ (has-predicate leased-world-pred-leaseholder LeasedResidenceWorld residential-shelter (leaseholder Resident LeaseAgreement)) (stv 0.85 0.8)))

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

;; V-predicate builder.
;;
;; It first builds the algebraic specification for the requested concept
;; and perspective. Then it extracts properties tagged with that same
;; perspective, expands each property through the possible-world mapping,
;; builds algebraic specs for those worlds, and returns compact world-spec
;; placeholders in the final V-predicate.

(= (build-world-spec-placeholder $world $perspective)
    (let $worldSpec (build-algebraic-spec $world $perspective)
        (WorldSpec $world $perspective)))

(= (possible-world-spec-set $property $perspective)
    (WorldSpecSet
        (collapse
            (match &self
                (: $worldEdge (≞ (property-possible-world $worldEdge $property $perspective $world) $worldTv))
                (build-world-spec-placeholder $world $perspective)))))

(= (v-predicate-properties $concept $perspective)
    (collapse
        (match &self
            (: $propertyEdge (≞ (has-property $propertyEdge $concept $perspective $property) $propertyTv))
            (match &self
                (: $degreeEdge (≞ (property-expressiveness $propertyEdge $degree) $degreeTv))
                ($property
                    (possible-world-spec-set $property $perspective)
                    $degree)))))

(= (build-v-predicate $concept $perspective)
    (let $conceptSpec (build-algebraic-spec $concept $perspective)
        (Concept $concept
            (perspective $perspective)
            (V-predicate
                (Property
                    (v-predicate-properties $concept $perspective))))))

!(println! "===== Build House spec under residential-shelter =====")
!(build-algebraic-spec House residential-shelter)

!(println! "===== Build House spec under economic-valuation =====")
!(build-algebraic-spec House economic-valuation)

!(println! "===== Build House spec under physical-structure =====")
!(build-algebraic-spec House physical-structure)

!(println! "===== Build Apartment spec under residential-shelter =====")
!(build-algebraic-spec Apartment residential-shelter)

!(println! "===== Build House V-predicate under residential-shelter =====")
!(build-v-predicate House residential-shelter)

!(println! "===== Build House V-predicate under economic-valuation =====")
!(build-v-predicate House economic-valuation)
