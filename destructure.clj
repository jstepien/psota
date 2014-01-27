;; Copyright (c) Rich Hickey. All rights reserved.
;; The use and distribution terms for this software are covered by the
;; Eclipse Public License 1.0 (http://opensource.org/licenses/eclipse-1.0.php)
;; which can be found in the file epl-v10.html at the root of this distribution.
;; By using this software in any fashion, you are agreeing to be bound by
;; the terms of this license.
;; You must not remove this notice, or any other, from this software.

(defn destructure [bindings]
  (let [invoke (fn [f & args] (apply f args))
        bents (partition 2 bindings)
        pb (fn pb [bvec b v]
             (let [pvec
                   (fn [bvec b val]
                     (let [gvec (gensym)]
                       (loop [ret (-> bvec (conj gvec) (conj val))
                              n 0
                              bs b
                              seen-rest? false]
                         (if (seq bs)
                           (let [firstb (first bs)]
                             (cond
                              (= firstb '&) (recur (pb ret (second bs) (list `nthnext gvec n))
                                                   n
                                                   (nnext bs)
                                                   true)
                              (= firstb :as) (pb ret (second bs) gvec)
                              :else (if seen-rest?
                                      (throw "Unsupported binding form, only :as can follow & parameter")
                                      (recur (pb ret firstb  (list `nth gvec n nil))
                                             (inc n)
                                             (next bs)
                                             seen-rest?))))
                           ret))))
                   pmap
                   (fn [bvec b v]
                     (let [gmap (gensym)
                           gmapseq (with-meta gmap {:tag 'clojure.lang.ISeq})
                           defaults (get b :or)
                           f (fn [ret]
                               (if (get b :as)
                                 (conj ret (get b :as) gmap)
                                 ret))]
                       (loop [ret (-> bvec (conj gmap) (conj v)
                                      (conj gmap) (conj `(if (seq? ~gmap) (clojure.lang.PersistentHashMap/create (seq ~gmapseq)) ~gmap))
                                      f)
                              bes (reduce
                                   (fn [bes entry]
                                     (reduce (fn [x y]
                                               (assoc x y (invoke (val entry) y)))
                                             (dissoc bes (key entry))
                                             (get bes (key entry))))
                                   (reduce dissoc b [:or :as])
                                   {:keys (comp keyword str)})]
                         (if (seq bes)
                           (let [bb (key (first bes))
                                 bk (val (first bes))
                                 has-default (contains? defaults bb)]
                             (recur (pb ret bb (if has-default
                                                 (list `or
                                                       (list `get gmap bk)
                                                       (get defaults bb))
                                                 (list `get gmap bk)))
                                    (next bes)))
                           ret))))]
               (cond
                (symbol? b) (-> bvec (conj b) (conj v))
                (vector? b) (pvec bvec b v)
                (map? b) (pmap bvec b v)
                :else (throw (str "Unsupported binding form: " b)))))
        process-entry (fn [bvec b] (pb bvec (first b) (second b)))]
    (if (every? symbol? (map first bents))
      bindings
      (reduce process-entry [] bents))))
