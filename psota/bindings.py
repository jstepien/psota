import builtins
import space

core_ns = "psota.core"
current_ns = "*ns*"

class Bindings:
    "Maintains mappings from vars to values in all nss."

    def __init__(self, st):
        core_mapping = {}
        for (sym, val) in builtins.core:
            var = space.W_Var(core_ns, sym, val)
            core_mapping[st.get_sym_id(sym)] = var
        self.vars = {core_ns: core_mapping}
        self.ns = core_ns
        self.st = st
        self.version = 0
        self.set(st.add_sym(current_ns), space.W_String(core_ns))

    def set_ns(self, ns):
        self.ns = ns
        if self.vars.get(ns, None) is None:
            vars = {}
            vars.update(self.vars[core_ns])
            self.vars[ns] = vars
        self.set(self.st.get_sym_id(current_ns), space.W_String(ns))

    def get(self, key):
        w_var = self.vars[self.ns].get(key, None)
        if w_var is not None:
            return w_var.w_val
        return self._qualified_sym(key)

    def _qualified_sym(self, key):
        sym = self.st.get_sym(key)
        idx = sym.find("/") + 1
        if idx <= 1:
            return
        ns_idx = idx - 1
        assert ns_idx >= 0
        ns = self.vars.get(sym[:ns_idx], None)
        if ns is None:
            return
        sym_id = self.st.get_sym_id(sym[idx:])
        if sym_id < 0:
            return
        w_var = ns.get(sym_id, None)
        if w_var is not None:
            return w_var.w_val

    def get_var(self, sym):
        assert isinstance(sym, str)
        key = self.st.get_sym_id(sym)
        return self.vars[self.ns][key]

    def set(self, key, val):
        var = space.W_Var(self.ns, self.st.get_sym(key), val)
        self.vars[self.ns][key] = var
        self.version += 1

    def alter_var(self, w_var, w_val):
        w_new_var = w_var.altered(w_val)
        key = self.st.get_sym_id(w_var.sym)
        self.vars[self.ns][key] = w_new_var
        self.version += 1
