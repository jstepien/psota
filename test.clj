(load "core.clj")

(defn fail
  [prefix success & expr]
  (print (str prefix ": "))
  (apply prn expr)
  (swap! success (fn [_] false)))

(defmacro tests
  [& exprs]
  (let [success-sym (gensym)]
    `(let [~success-sym (atom true)]
       ~(cons 'do
              (map (fn [expr]
                     `(try
                        (when-not ~expr
                          (fail "F" ~success-sym '~expr))
                        (catch Throwable ~'e
                          (fail "E" ~success-sym '~expr '-> ~'e))))
                   exprs))
       (when-not (deref ~success-sym)
         (println "Some tests failed!")
         (throw "fail")))))

(tests

  ;; seqs
  (every? (comp not seq)
          [nil () [] (lazy-seq ()) "" {} (hash-map)])
  (every? (comp (partial = ()) rest)
          [nil () [] (lazy-seq ()) "" {} (hash-map)])
  (every? (comp not first)
          [nil () [] (lazy-seq ()) "" {} (hash-map)])
  (= () [])
  (not (= () nil))
  (not (= [] nil))

  ;; maps
  (= 1 (get {:a 1 :b 2} :a))
  (not (get {:a 1 :b 2} :c))
  (= 3 (get {:a 1 :b 2} :c 3))
  (= {} (dissoc {:a 1} :a)))