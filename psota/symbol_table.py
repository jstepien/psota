import builtins

class SymbolTable:
    def __init__(self):
        self.sym_ids = {}
        self.syms = []
        self.init_core()
        for (sym, _) in builtins.consts:
            self.syms.append(sym)
            self.sym_ids[sym] = len(self.syms) - 1
        self.fns = []
        self.macros = {}

    def init_core(self):
        for (sym, _) in builtins.core:
            self.add_sym(sym)

    def add_sym(self, sym):
        assert isinstance(sym, str)
        if sym in self.sym_ids:
            return self.sym_ids[sym]
        id = len(self.syms)
        self.syms.append(sym)
        self.sym_ids[sym] = id
        return id

    def get_sym_id(self, sym):
        assert isinstance(sym, str)
        return self.sym_ids[sym]

    def get_sym(self, id):
        assert isinstance(id, int)
        return self.syms[id]

    def add_macro(self, name, fn_id):
        self.macros[name] = fn_id

    def get_macro(self, macro):
        return self.macros[macro]

    def has_macro(self, macro):
        return macro in self.macros

    def add_fn(self, fn):
        self.fns.append(fn)
        return len(self.fns) - 1

    def get_fn(self, fn):
        assert fn < len(self.fns)
        return self.fns[fn]
