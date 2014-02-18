(defmacro* defmacro
  [& args]
  (cons 'defmacro* args))

(defmacro fn
  [& args]
  (if (symbol? (first args))
    (let* storage (gensym)
      `(let [~storage (atom nil)
             ~(first args) (fn* [& args]
                             (apply (deref ~storage) args))]
         (swap! ~storage
                (fn* [_]
                  ~(cons 'fn* (rest args))))))
    (cons 'fn* args)))

(defmacro def
  [& args]
  (if (= '^ (first args))
    `(do
      (def* ~(rest (rest args)))
      (alter-meta!
       (var ~(first (rest (rest args))))
       (fn [_] ~(first (rest args)))))
    (cons 'def* args)))

(defmacro defn
  [name args & body]
  `(def ~name ~(cons 'fn (cons args body))))

(defn not (x) (if x false true))

(defmacro when
  [cond & body]
  `(if ~cond ~(cons 'do body) nil))

(defmacro when-not
  [cond & body]
  `(when (not ~cond) ~(cons 'do body)))

(defmacro comment [& _] 'nil)

(defn reduce [f init coll]
  (if (= coll ())
    init
    (recur f (f init (first coll)) (rest coll))))

(defn count
  [coll]
  (reduce (fn [acc _] (+ acc 1)) 0 coll))

(defn last
  [coll]
  (reduce (fn [_ x] x) nil coll))

(defn comp
  [f & fs]
  (if (= () fs)
    f
    (fn [& args]
      (f (apply (apply comp fs) args)))))

(def second (comp first rest))

(defmacro let
  [bindings & body]
  (if (= bindings ())
    (cons 'do body)
    `(let*
       ~(first bindings)
       ~(second bindings)
       ~(cons 'let
              (cons (rest (rest bindings))
                    body)))))

(defmacro cond*
  [pairs]
  (let [condition (first pairs)
        result (second pairs)
        otherwise (rest (rest pairs))]
    `(if ~condition
       ~result
       ~(if (= () otherwise)
          'nil
          `(cond* ~otherwise)))))

(defmacro cond
  [& pairs]
  `(cond* ~pairs))

(defmacro or
  [hd & tl]
  (if (= () tl)
    hd
    `(if ~hd
       ~hd
       ~(cons 'or tl))))

(defmacro and
  [hd & tl]
  (if (= () tl)
    hd
    `(if ~hd
       ~(cons 'and tl)
       ~hd)))

(defn dec
  [x]
  (- x 1))

(defn take
  [n coll]
  (if (or (= 0 n)
          (= coll ()))
    ()
    (cons (first coll)
          (take (dec n)
                (rest coll)))))

(defn drop
  [n coll]
  (if (or (= 0 n)
          (= coll ()))
    coll
    (drop (dec n)
          (rest coll))))

(defn partition
  [n coll]
  (if (= () coll)
    ()
    (cons (take n coll)
          (partition n (drop n coll)))))

(defmacro lazy-seq
  [coll]
  `(lazy-seq* (fn [] ~coll)))

(defn map [f coll]
  (if (= coll ())
    ()
    (lazy-seq
      (cons (f (first coll))
            (map f (rest coll))))))

(defn vec
  [coll]
  (apply vector coll))

(defmacro loop
  [bindings & body]
  (let [pairs (partition 2 bindings)
        args (map first pairs)
        inits (map second pairs)
        sym (gensym)]
    `(let [~sym (fn ~(vec args)
                 ~(cons 'do body))]
      ~(cons sym inits))))

(defn reverse
  [coll]
  (loop [reversed ()
         tail coll]
    (if (= tail ())
      reversed
      (recur (cons (first tail) reversed)
             (rest tail)))))

(defn concat
  [xs ys]
  (lazy-seq
   (if (= ys ())
     xs
     (reverse
      (reduce (fn [acc el]  (cons el acc))
              (reverse xs)
              ys)))))

(defn conj [xs x]
  (if (vector? xs)
    (vec (concat xs [x]))
    (cons x xs)))

(defmacro ->
  [x & ops]
  (if (= () ops)
    x
    (let [hd (first ops)
          tl (rest ops)
          current (if (symbol? hd)
                    (list hd x)
                    (cons (first hd) (cons x (rest hd))))]
      (cons '-> (cons current tl)))))

(defn seq [coll]
  (when-not (= () coll)
    coll))

(def next (comp seq rest))

(def nnext (comp next next))

(defn nthnext
  [coll n]
  (if (= 0 n)
    coll
    (recur (next coll) (- n 1))))

(defn nth
  [coll n not-found]
  (cond
    (= 0 n) (first coll)
    (= () coll) not-found
    :else (recur (next coll) (- n 1) not-found)))

(defn every?
  [f coll]
  (loop [xs coll]
    (cond
     (= () xs) true
     (f (first xs)) (recur (rest xs))
     :else false)))

(defn inc
  [n]
  (+ 1 n))

(def key first)
(def val second)

(defn contains?
  [coll key]
  (not (not (get coll key))))

(def seq? list?)

(load "destructure.clj")

(defmacro* defmacro
  [name args body]
  (let [orig-args (gensym)]
    `(defmacro* ~name
       [& ~orig-args]
       (let ~(destructure (vector args orig-args))
         ~body))))

(defmacro let-destructured
  [bindings & body]
  (if (= bindings ())
    (cons 'do body)
    `(let*
       ~(first bindings)
       ~(second bindings)
       ~(cons 'let-destructured
              (cons (rest (rest bindings))
                    body)))))

(defmacro let
  [bindings & body]
  (cons 'let-destructured (cons (destructure bindings) body)))

(defmacro fn-destructure
  [args & body]
  (if (every? symbol? args)
    (cons 'fn* (cons args body))
    (let [orig-args (gensym)]
      `(fn* [& ~orig-args]
         (let ~(destructure (vector args orig-args))
           ~(cons 'do body))))))

(defmacro fn-with-single-arity
  [& args]
  (if (symbol? (first args))
    (let* storage (gensym)
      `(let [~storage (atom nil)
             ~(first args) (fn* [& args]
                             (apply (deref ~storage) args))]
         (swap! ~storage
                (fn* [_]
                  ~(cons 'fn-destructure (rest args))))))
    (cons 'fn-destructure args)))

(defn zipmap
  [keys vals]
  (loop [acc {}
         keys (seq keys)
         vals (seq vals)]
    (if (and keys vals)
      (recur (assoc acc (first keys) (first vals))
             (next keys)
             (next vals))
      acc)))

(defmacro fn
  [& args]
  (cond
    (or (vector? (first args))
        (symbol? (first args))) (cons 'fn-with-single-arity args)
    (every? list? args)
    (if (= 1 (count args))
      (cons 'fn (first args))
      (let [arities (map (comp count first) args)
            fns (map (fn [tail] (cons 'fn tail)) args)
            variants (gensym)]
        `(let [~variants ~(zipmap arities fns)]
           (fn-with-single-arity
             [& coll]
             (let [nargs (count coll)
                   f (get ~variants nargs)]
               (if f
                 (apply f coll)
                 (throw (str "Incorrect arity: " nargs))))))))
    :else (throw "Unsupported fn form")))

(defn partial
  [f & xs]
  (fn [& ys] (apply f (concat xs ys))))

(def zero? (partial = 0))

(defn range
  [n]
  (let [chunk-size 1
        helper (fn f [s e]
                 (if (= s e)
                   ()
                   (lazy-seq (cons s (f (+ s chunk-size) e)))))]
    (helper 0 n)))

(defmacro var
  [sym]
  `(var* (quote ~sym)))

(def get-in
  (partial reduce (fn [m cur] (get m cur))))

(defn protocol-call
  [protocol protocol-name fname args]
  (let [first-arg (first args)
        type (class first-arg)
        f (or (get-in protocol [type fname])
              (and (map? first-arg)
                   (get-in first-arg [protocol-name fname]))
              (throw (str first-arg " doesn't implement " protocol-name)))]
    (apply f args)))

(defmacro defprotocol
  [name [fname args]]
  `(do
    (def ~name {})
    (defn ~fname
      ~args
      (protocol-call ~name
                     (quote ~name)
                     (quote ~fname)
                     ~args))))

(defn extend
  [type proto funs]
  (alter-var-root proto
                  (fn [p] (assoc p type funs))))

(defmacro reify
  [protocol [fname & frest]]
  `{(quote ~protocol)
    {(quote ~fname) ~(cons 'fn frest)}})

(defn reset!
  [atom val]
  (swap! atom (fn [_] val)))

(defn print [& coll]
  (reduce (fn [first obj]
            (do
             (when-not first
               (print1 " "))
             (print1 obj)))
          true
          coll))

(defn println [& coll]
  (apply print coll)
  (print "\n"))

(defprotocol Pr
  (pr* [x]))

(let [pr*-as-str {'pr* str}]
  ;; Poor man's doseq
  (last
    (map (fn [specimen] (extend (class specimen) (var Pr) pr*-as-str))
         [nil 1 :kw 'sym true println (class ())])))

(extend (class \a)
  (var Pr) {'pr* (fn [c]
                   (let [s (str c)]
                     (cond
                       (= " " s) "\\space"
                       (= "\n" s) "\\newline"
                       :else (str "\\" s))))})

(let [classes (map class [[] () (lazy-seq ())])
      punctuation (zipmap classes
                          [["[" "]"] ["(" ")"] ["(" ")"]])
      impl {'pr* (fn [coll]
                   (let [[open close] (get punctuation (class coll))]
                     (str
                       (reduce (fn [acc el]
                                 (str acc
                                      (if (= open acc)
                                        ""
                                        " ")
                                      (pr* el)))
                               open
                               coll)
                       close)))}]
  ;; Poor man's doseq
  (last (map (fn [cls] (extend cls (var Pr) impl))
             classes)))

(let [impl {'pr* (fn [map]
                   (str
                     (reduce (fn [acc [key val]]
                               (str acc
                                    (if (= "{" acc)
                                      ""
                                      " ")
                                    (pr* key)
                                    " "
                                    (pr* val)))
                             "{"
                             map)
                     "}"))}]
  ;; Poor man's doseq
  (last (map (fn [specimen] (extend (class specimen) (var Pr) impl))
             [(array-map) (hash-map)])))

(extend (class "")
  (var Pr) {'pr* (fn [s] (str "\"" s "\""))})

(defn pr [& args]
  (apply print (map pr* args)))

(defn prn [& args]
  (apply println (map pr* args)))

(defmacro try
  [& forms]
  (let [forms-number (count forms)
        maybe-catch (last forms)
        got-catch (and (first maybe-catch)
                       (= 'catch (first maybe-catch)))]
    (if got-catch
      `(try*
        (fn* [] ~(cons 'do (take (- forms-number 1) forms)))
        (fn* [~(second maybe-catch)] ~(cons 'do (drop 2 maybe-catch))))
      (cons 'do forms))))

(defn repl []
  (print (str *ns* "=> "))
  (let [line (getline)]
    (if (= "" line)
      (println)
      (do
        (try
          (-> line read-string eval prn)
          (catch e
            (prn [:caught e])))
        (recur)))))

(in-ns 'user)
(repl)
