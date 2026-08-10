
!(import! &self GeneralizationDTLTest)
!(import! &self synthesizers)

(: build-algebraic-spec (-> $space $concept (-> Atom) (-> Atom) Nat Atom))
(= (build-algebraic-spec $space $concept $kb $rb $max-depth)
    (let* (
                ;; collect generalization path for the main concept using the provided KB
                ($gen-path (collapse (generalization-path-finder $concept $kb $max-depth 0 ($concept))))

                ;; expand related concepts by following generalization paths for each node
                ($expanded (expand-related-by-paths $space $gen-path $kb $max-depth))

                ;; extract operators and axioms from the provided atomspace and rulebase
                ($ops-space (extract-operators $space))
                ($ops-rb (extract-operators $rb))
                ($ops (collapse (superpose ($ops-space) ($ops-rb))))
                ($ops (if (== $ops ()) (synthesize-ops-if-missing $space $kb $rb $max-depth) $ops))
                ($axiom (collapse (extract-axioms $space)))
                ($axiom (if (== $axiom ()) (synthesize-axiom-if-missing $space $kb $rb $max-depth) $axiom))
                ;;predicates from space and rulebase
                ($preds-space (extract-predicates $space))
                ($preds-rb (extract-predicates $rb))
                ($preds (collapse (superpose ($preds-space) ($preds-rb))))
                ($preds (if (== $preds ()) (synthesize-preds-if-missing $space $kb $rb $max-depth) $preds))

                ;; sorts → nodes from the expanded related set
                ($sorts $expanded)
             )
         ;; return  AlgebraicSpec atom: (: AlgebraicSpec (sorts ops axioms preds))
         (cons-atom AlgebraicSpec (collapse(superpose(($sorts) ($ops) ($axiom) ($preds)))))
    )
)


(: expand-related-by-paths (-> Atom Atom (-> Atom) Nat Atom))
(= (expand-related-by-paths $space $paths $kb $max-depth)
   ;; For each node in $paths, gather its generalization path up to $max-depth
   (let $collector
     (collapse
       (foldl-atom $paths () $acc $node
         (let $gp (collapse (generalization-path-finder $node $kb $max-depth 0 ($node)))
           (collapse (superpose ($acc) ($gp)))))))
)



(: extract-operators (-> Atom))
(= (extract-operators $space)
(let $ops (: $conceptm (≞ $concept $STV)) (match $space $ops (collapse $ops)))
   ;; Find atoms that look like operator `(: name (-> ))`
   
)


(: extract-predicates (-> Atom))
(= (extract-predicates $space)
   ;; Find simple predicate declarations like `(: name Predicate)`
   (let $pred (: $concept Predicate) (match $space $pred (collapse $pred)))
  )

;axiom
(: extract-axioms (-> Atom))
(= (extract-axioms $space)
   ;; Find  axioms: (≞ ) atoms and other constraints

   (let $axiom (: $conceptm (≞ $concept $stv)) (match &self $axiom (collapse(superpose (≞ $concept $stv)))))
   
)

(: spec-from-paths (-> Atom Atom))
(= (spec-from-paths $space $paths)
   ;; Build preliminary signature: each path node becomes a sort
   (let $sorts (map-atom $paths $x $x)
     (cons-atom Spec $sorts)))

(: synthesize-ops-if-missing (-> Atom (-> Atom) (-> Atom) Nat Atom))
(= (synthesize-ops-if-missing $space $kb $rb $max-depth)
    ;; Try to synthesize operatorlike atoms when none are found via pattern matching
    ;; the goal asks the synthesizer to propose atoms
    ;;  results are returned collapsed
    (let $goal (: $proposal (≞ $x $stv))
       (collapse (synthesize $goal $kb $rb (S Z)))))

(: synthesize-axiom-if-missing (-> Atom (-> Atom) (-> Atom) Nat Atom))
(= (synthesize-axiom-if-missing $space $kb $rb $max-depth)
   ;; Synthesize axiom atoms when none are available
   (let $goal (: $proposal (≞ $x $stv))
     (collapse (synthesize $goal $kb $rb (S Z)))))

(: synthesize-preds-if-missing (-> Atom (-> Atom) (-> Atom) Nat Atom))
(= (synthesize-preds-if-missing $space $kb $rb $max-depth)
   ;; Synthesize predicate declarations when missing 
   (let $goal (: $proposal Predicate);
     (collapse (synthesize $goal $kb $rb (S Z)))))



;!(build-algebraic-spec &kb bird kb rb 2)