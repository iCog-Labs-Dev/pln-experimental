; !(register-module! ../../../metta)
!(import! &self ../../../../PeTTa/lib/lib_import)
;; Import modules
!(import! &self ../../../metta/pln/dependent-types/GeneralizationDTLhelper)
!(import! &self ../../../metta/pln/dependent-types/GeneralizationDTL)
!(static-import! &kb ../../../metta/pln/dependent-types/GeneralizationKB/lcg_kb)
!(import! &self ../../../metta/common/truthvalue/MeasEq)
; !(import! &self metta:common:formula:DeductionFormula)
!(import! &self ../../../metta/common/truthvalue/TruthValue)
; !(import! &self ../../../metta/common/Num)
; !(import! &self ../../../metta/synthesis/Synthesize)
!(import! &self synthesizers)
!(import! &self ../../../metta/common/Record)
!(import! &self ../../../metta/pln/dependent-types/llm)
!(import! &self "lcggenerator.py")
; !(let $lcgs (py-call (lcggenerator.generate_lcg_rules 2)) (let $slcgs (sread $lcgs) (superpose $slcgs)))
; !(import! &self metta:pln:dependent-types:helper)

!(println! "KB loaded")
(: Predicate Type)
(: → (-> Predicate %Undefined% Expression Type))
(: water Predicate)
(: land Predicate)
(: medium Predicate)
(: surface Predicate)

(: kb (-> Atom))
(= (kb) (get-atoms &kb))
(: rb (-> Atom))
; (= (rb) (double-depth-lcg-rule))
(= (rb) (let $lcgs (py-call (lcggenerator.generate_lcg_and_write_synthesizers 2 "synthesizers.metta")) (let $slcgs (sread $lcgs) (eval (superpose $slcgs)))))
; !(rb)

(= (generalization-path-finder-helper $concept $kb $result)
    (let (: $proof (≞ (→ $concept $gen ()) (STV $s $c))) ($kb) (let $updated-result (union-atom $result (-> $gen)) ($gen $updated-result)))
)

(= (generalization-path-finder $concept $kb $max-depth $counter $result)
        (if (== $counter $max-depth)
            $result
            (let* 
                (
                    ($imt (collapse(generalization-path-finder-helper $concept $kb $result)))
                    (($new-concept $new-result) (if (== (size-atom $imt) 1) (car-atom $imt) (() $result)))
                    ($new-counter (+ $counter 1))
                    ($gen-path (generalization-path-finder $new-concept $kb $max-depth $new-counter $new-result))
                )
                $gen-path
            )
        )
)

(= (proof-generator $concept)
    (if (== (get-metatype $concept) Symbol) (py-call (operator.add $concept m)) ())
)

(= (proof-generator $concept1 $concept2)
    (if (and (== (get-metatype $concept1) Symbol) (== (get-metatype $concept2) Symbol)) (let $c1c2 (py-call (operator.add $concept1 $concept2)) (proof-generator $c1c2)) ())
)

(= (new-lcg-adder $space ($concept1l $lcg $concept1r) ($concept2l $lcg $concept2r) ($c1llcgstv $lcgc1rstv) ($c2llcgstv $lcgc2rstv))
    (let*
        (
            (($c1llcgp $lcgc1rp $c2llcgp $lcgc2rp $lcgp) (collapse(superpose((proof-generator $concept1l $lcg) (proof-generator $lcg $concept1r) (proof-generator $concept2l $lcg) (proof-generator $lcg $concept2r) (proof-generator $lcg)))))
            ($addpath (collapse(superpose((add-atom $space (: $c1llcgp (≞ (→ $concept1l $lcg ()) $c1llcgstv))) (if (== (get-metatype $concept1r) Symbol) (add-atom $space (: $lcgc1rp (≞ (→ $lcg $concept1r ()) $lcgc1rstv))) ()) (add-atom $space (: $c2llcgp (≞ (→ $concept2l $lcg ()) $c2llcgstv))) (if (== (get-metatype $concept2) Symbol) (add-atom $space (: $lcgc2rp (≞ (→ $lcg $concept2r ()) $lcgc2rstv))) ())))))
            ($_ (println! (Add-path $addpath)))
            ($removeoldpath (collapse(superpose((remove-atom $space (: $c1lc1rproof (≞ (→ $concept1l $concept1r ()) $c1lc1rstv))) (remove-atom $space (: $c2lc2rproof (≞ (→ $concept2l $concept2r ()) $c2lc2rstv)))))))
            ($_ (println! (Remove-old-path $removeoldpath)))
            ($addlcgcondly (collapse(let $prevlcg (collapse(match $space (: $lcgp (≞ $lcg $stv)) True)) (if (== $prevlcg (True)) $lcg (add-atom $space (: $lcgp (≞ $lcg (STV 0.5 0.5))))))))
            ($_ (println! (Add-lcg-condly $addlcgcondly)))
        )
        (if (and (== (get-metatype $addpath) Expression) (and (== (get-metatype $addlcgcondly) Expression) (== (get-metatype $removeoldpath) Expression))) (New Lcg has been added successfuly) (There was an error while adding Lcg, please try again!))
    )
)

(= (pair-lcg $concept1 $concept2 $kb $space $max-depth)
    (let $res (collapse (synthesize (: $proof (≞ (→ $concept1 $concept2 ($lcg)) $tv)) $space rb (S Z)))
            (if (== $res ())
                    (let ($c1-gen-path $c2-gen-path) (collapse(superpose((generalization-path-finder $concept1 kb $max-depth 0 ($concept1)) (generalization-path-finder $concept2 kb $max-depth 0 ($concept2))))) 
                        (if (or (and (== (size-atom $c1-gen-path) 1) (> (size-atom $c2-gen-path) 1)) (and (> (size-atom $c1-gen-path) 1) (== (size-atom $c2-gen-path) 1)))
                            (let ($c1lcgpath $c2lcgpath $c1stvs $c2stvs) (sread (useGenAI partialpathlcgprompt ($concept1 $c1-gen-path) ($concept2 $c2-gen-path))) 
                                (new-lcg-adder $space $c1lcgpath $c2lcgpath $c1stvs $c2stvs)
                            )
                            (let ($c1lcgpath $c2lcgpath $c1stvs $c2stvs) (sread (useGenAI fullpathlcgprompt ($concept1 $c1-gen-path) ($concept2 $c2-gen-path))) 
                                (new-lcg-adder $space $c1lcgpath $c2lcgpath $c1stvs $c2stvs)
                            )
                        )
                    )
                    $res
            )
    )
)

(= (get-alg-spec-part $alg-spec $part)
    (let (Concept $concept-name (spec (sorts $sorts) (ops $ops) (preds $preds) (axioms $axioms))) $alg-spec
        (if (== $part sorts)
            $sorts
            (if (== $part ops)
                $ops
                (if (== $part preds)
                    $preds
                    $axioms
                )
            )
        )
    )
)

(= (input-spec1) 
    (Concept House
        (spec
            (sorts (
                (Object 1.0) 
                (Structure 0.9) 
                ((House < Structure) 1.0)
            ))
            (ops (
                ((house : House) 1.0) 
                ((resident : Person) 0.8) 
                ((garden : ExternalSpace) 0.4)
            ))
            (preds (
                ((providesShelter House) 0.95)
                ((hasColor House Color) 0.2)
            ))
            (axioms (
                ((providesShelter (house)) 0.95)
            ))
        )
    )
)

(= (input-spec2) 
    (Concept House
        (spec
            (sorts (
                (Object 1.0) 
                (Structure 0.9) 
                ((House < Structure) 1.0)
            ))
            (ops (
                ((house : House) 1.0) 
                ((resident : Person) 0.8) 
                ((garden : ExternalSpace) 0.4)
            ))
            (preds (
                ((providesShelter House) 0.95)
                ((hasColor House Color) 0.2)
            ))
            (axioms (
                ((providesShelter (house)) 0.95)
            ))
        )
    )
)

(= (main-lcg $c1-alg-spec $c2-alg-spec)
    (let ($c1-sort $c2-sort) (collapse(superpose((get-alg-spec-part $c1-alg-spec ops) (get-alg-spec-part $c2-alg-spec ops))))
        ($c1-sort $c2-sort)
    )
)

!(main-lcg (input-spec1) (input-spec2))

; !(get-atoms &kb)

; !(pair-lcg sparrow airplane kb &kb 10)

; !(get-atoms &kb)
