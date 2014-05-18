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
  (= {} (dissoc {:a 1} :a))

  ;; for
  (= [[0 0] [0 1] [1 0] [1 1] [2 0] [2 1] [3 0] [3 1]]
     (for [x (range 4) y (range 2)] [x y]))

  ;; recur in a fn with rest args
  (let [xss (atom ())
        f (fn [& xs]
            (swap! xss conj xs)
            (when (seq xs)
              (recur (next xs))))]
    (f 1 2 3)
    (= [nil [3] [2 3] [1 2 3]]
       (deref xss)))

  (do
    "Still doesn't work."
    (comment
      ((fn [[x & xs]]
         (if (= 3 x)
           x
           (recur xs)))
       [1 2 3]))
    1)

  ;; quasi quoting
  (eval `(= 'a# 'a#))
  (not (= `a# `a#)))
