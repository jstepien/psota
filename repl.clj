(load "core.clj")

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
