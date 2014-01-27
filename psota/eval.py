from rpython.rlib import jit

import space
import builtins

core_ns = "psota.core"

class Bindings:
    def __init__(self, st):
        core_mapping = {}
        for (sym, val) in builtins.core:
            var = space.W_Var(core_ns, sym, val)
            core_mapping[st.get_sym_id(sym)] = var
        self.vars = {core_ns: core_mapping}
        self.ns = core_ns
        self.st = st
        self.version = 0
        self.set(st.add_sym("*ns*"), space.W_String(core_ns))

    def set_ns(self, ns):
        self.ns = ns
        if self.vars.get(ns, None) is None:
            vars = {}
            vars.update(self.vars[core_ns])
            self.vars[ns] = vars
        self.set(self.st.get_sym_id("*ns*"), space.W_String(ns))

    def get(self, key):
        w_var = self.vars[self.ns].get(key, None)
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

@jit.elidable
def _get_index(indices, key, version):
    return indices.get(key, -1)

class Env:
    def __init__(self, inits, parent=None):
        self.parent = parent
        if parent is None:
            self.indices = {}
            self.version = 0
            self.slots = []
        else:
            self.indices = parent.indices
            self.version = parent.version
            self.slots = [None for _ in range(len(parent.slots))]
        self.on_stack = False
        for (key, val) in inits:
            self.set(key, val)

    def mark_used(self):
        self.on_stack = True

    def mark_free(self):
        self.on_stack = False

    def set(self, key, val):
        indices = jit.promote(self.indices)
        key = jit.promote(key)
        version = jit.promote(self.version)
        index = _get_index(indices, key, version)
        if index == -1:
            parent = self.parent
            if parent is not None and self.indices is parent.indices:
                self.indices = {}
                self.indices.update(parent.indices)
            self.indices[key] = len(self.slots)
            self.slots.append(val)
            self.version += 1
        else:
            self.slots[index] = val

    def get(self, key):
        indices = jit.promote(self.indices)
        key = jit.promote(key)
        version = jit.promote(self.version)
        index = _get_index(indices, key, version)
        if index >= 0:
            val = self.slots[index]
            if val is None and self.parent is not None:
                return self.parent.get(key)
            return val
        if self.parent is not None:
            return self.parent.get(key)

    def clone(self):
        inits = [(id, self.slots[self.indices[id]])
                for id in self.indices.keys()]
        return Env(inits, self)

def base_env(st):
    return Env(inits=[(st.get_sym_id(sym), val)
                      for (sym, val) in builtins.consts])

(
        OP_KEYWORD,
        OP_IF,
        OP_PUSH_ENV,
        OP_POP_ENV,
        OP_SYM,
        OP_INT,
        OP_QUOTE,
        OP_RELJMP,
        OP_FN,
        OP_INVOKE,
        OP_DEF,
        OP_PUSH,
        OP_APPLY,
        OP_RECUR,
        OP_STRING,
        OP_TRY,
        ) = range(16)

@jit.elidable
def lookup_in_bindings(bindings, version, sym_id):
    return bindings.get(sym_id)

def lookup(env, bindings, sym_id):
    val = env.get(sym_id)
    if val is None:
        val = lookup_in_bindings(bindings, jit.promote(bindings.version), sym_id)
    if val is None:
        raise space.LookupException("Undefined symbol: %s" %
                bindings.st.get_sym(sym_id))
    return val


@jit.elidable
def is_true(obj):
    return not(obj == space.w_nil or obj == space.w_false)

ops_names = {
        OP_KEYWORD: 'KEYWORD',
        OP_IF: 'IF',
        OP_PUSH_ENV: 'PUSH_ENV',
        OP_POP_ENV: 'POP_ENV',
        OP_SYM: 'SYM',
        OP_INT: 'INT',
        OP_QUOTE: 'QUOTE',
        OP_RELJMP: 'RELJMP',
        OP_FN: 'FN',
        OP_INVOKE: 'INVOKE',
        OP_DEF: 'DEF',
        OP_PUSH: 'PUSH',
        OP_APPLY: 'APPLY',
        OP_RECUR: 'RECUR',
        OP_STRING: 'STRING',
        OP_TRY: 'TRY',
        }

def code_to_str(code):
    val = ""
    for op in code:
        if op in ops_names:
            val += ops_names[op]
        else:
            val += str(op)
        val += " "
    return val

def get_location(ip, code):
    assert ip >= 0
    before = code_to_str(code[max(ip - 5, 0) : ip])
    after = code_to_str(code[ip + 1 : ip + 6])
    this = code_to_str([code[ip]])
    return before + "(" + this + ")" + after

jitdriver = jit.JitDriver(
        greens=["ip", "code"],
        reds=["sp", "stack", "bindings", "r1", "st", "env"],
        get_printable_location=get_location,
        )

def invoke_fn(w_fn, args_w, bindings):
    w_fn = space.cast(w_fn, space.W_Fun)
    inits = []
    argc = len(args_w)
    arg_ids_len = len(w_fn.arg_ids)
    if argc > arg_ids_len and w_fn.got_rest_args():
        rest_args = [args_w.pop() for _ in range(argc - arg_ids_len)]
        rest_args.reverse()
        inits.append((w_fn.rest_args_id, space.wrap(rest_args)))
    elif w_fn.got_rest_args():
        inits.append((w_fn.rest_args_id, space.w_empty_list))
    args = [args_w.pop() for _ in range(arg_ids_len)]
    idx = 0
    env = Env([], w_fn.env)
    for arg_id in reversed(w_fn.arg_ids):
        env.set(arg_id, args[idx])
        idx += 1
    return eval(env, bindings, bindings.st, w_fn.code)

@jit.unroll_safe
def invoke(ip, env, code, r1, stack, sp, bindings):
    ip += 1
    sp = jit.promote(sp)
    argc = jit.promote(get_op(code, ip))
    assert argc >= 0
    fn = jit.promote(r1)
    if isinstance(fn, space.W_BIF):
        new_sp = sp - argc
        assert new_sp >= 0
        args = [space.w_nil for _ in range(argc)]
        for i in range(new_sp, sp):
            args[i - new_sp] = stack[i]
        ret = fn.invoke(args, bindings)
        if ret is None:
            ret = space.w_nil
        return ret
    elif isinstance(fn, space.W_Fun):
        arg_ids_len = const_len(fn.arg_ids)
        if fn.env.on_stack:
            new_env = Env([], fn.env)
        else:
            new_env = fn.env
        try:
            new_env.mark_used()
            if (argc < arg_ids_len or
                    (argc > arg_ids_len and not fn.got_rest_args())):
                raise space.ArityException(arg_ids_len, argc)
            if argc > arg_ids_len and fn.got_rest_args():
                new_sp = sp - (argc - arg_ids_len)
                assert new_sp >= 0
                rest_args = [space.w_nil for _ in range(argc - arg_ids_len)]
                for i in range(new_sp, sp):
                    rest_args[i - new_sp] = stack[jit.promote(i)]
                sp = new_sp
                new_env.set(fn.rest_args_id, space.wrap(rest_args))
            elif fn.got_rest_args():
                new_env.set(fn.rest_args_id, space.w_empty_list)
            sp -= arg_ids_len
            idx = 0
            for arg_id in fn.arg_ids:
                new_env.set(arg_id, stack[jit.promote(idx + sp)])
                idx += 1
            return eval(new_env, bindings, bindings.st, fn.code)
        finally:
            new_env.mark_free()
    else:
        raise space.SpaceException("Cannot invoke %s" % fn.to_str())

@jit.unroll_safe
def apply(ip, env, code, r1, stack, sp, bindings):
    ip += 1
    assert code[ip] == 2
    new_sp = sp - 2
    assert new_sp >= 0
    (fn, w_args) = stack[new_sp : sp]
    sp = new_sp
    args = space.unwrap(w_args)
    argc = len(args)
    if isinstance(fn, space.W_BIF):
        ret = fn.invoke(args, bindings)
        if ret is None:
            ret = space.w_nil
        return ret
    elif isinstance(fn, space.W_Fun):
        arg_ids_len = len(fn.arg_ids)
        if fn.env.on_stack:
            new_env = Env([], fn.env)
        else:
            new_env = fn.env
        try:
            new_env.mark_used()
            if (argc < arg_ids_len or
                    (argc > arg_ids_len and not fn.got_rest_args())):
                raise space.ArityException(arg_ids_len, argc)
            if argc > arg_ids_len and fn.got_rest_args():
                rest_args = [args.pop() for _ in range(argc - arg_ids_len)]
                rest_args.reverse()
                new_env.set(fn.rest_args_id, space.wrap(rest_args))
            elif fn.got_rest_args():
                new_env.set(fn.rest_args_id, space.w_empty_list)
            idx = 0
            for arg_id in fn.arg_ids:
                new_env.set(arg_id, args[idx])
                idx += 1
            return eval(new_env, bindings, bindings.st, fn.code)
        finally:
            new_env.mark_free()
    else:
        raise space.SpaceException("Cannot apply %s" % fn.to_str())

@jit.elidable
def get_op(code, ip):
    return code[ip]

@jit.elidable
def const_len(code):
    return len(code)

stack_size = 100

def eval(env, bindings, st, code):
    ip = 0
    stack = [None for _ in range(stack_size)]
    sp = 0
    r1 = space.w_nil
    while ip < const_len(code):
        jitdriver.jit_merge_point(
                ip=ip,
                sp=sp,
                stack=stack,
                st=st,
                env=env,
                bindings=bindings,
                code=code,
                r1=r1,
                )
        assert r1 is not None
        assert sp >= 0
        op = get_op(code, ip)
        if op == OP_IF:
            ip += 1
            if not is_true(r1):
                ip += get_op(code, ip)
        elif op == OP_SYM:
            ip += 1
            r1 = lookup(env, jit.promote(bindings), get_op(code, ip))
        elif op == OP_KEYWORD:
            ip += 1
            r1 = space.W_Keyword(st.get_sym(get_op(code, ip)))
        elif op == OP_STRING:
            ip += 1
            r1 = space.W_String(st.get_sym(get_op(code, ip)))
        elif op == OP_INT:
            ip += 1
            r1 = space.W_Int(get_op(code, ip))
        elif op == OP_PUSH_ENV:
            ip += 1
            env = Env([(get_op(code, ip), r1)], env)
        elif op == OP_POP_ENV:
            env = env.parent
        elif op == OP_QUOTE:
            ip += 1
            r1 = space.W_Sym(st.get_sym(get_op(code, ip)))
        elif op == OP_RELJMP:
            ip += get_op(code, ip + 1) + 1
        elif op == OP_FN:
            ip += 1
            r1 = st.get_fn(get_op(code, ip)).with_env(env)
        elif op == OP_PUSH:
            stack[jit.promote(sp)] = r1
            sp += 1
        elif op == OP_DEF:
            ip += 1
            bindings.set(get_op(code, ip), r1)
        elif op == OP_RECUR:
            ip += 1
            argc = jit.promote(get_op(code, ip))
            sp -= argc
            idx = argc - 1
            while idx >= 0:
                ip += 1
                env.set(get_op(code, ip), stack[jit.promote(idx + sp)])
                idx -= 1
            ip = -1
        elif op == OP_INVOKE:
            r1 = invoke(ip, env, code, r1, stack, sp, bindings)
            ip += 1
            sp -= get_op(code, ip)
        elif op == OP_APPLY:
            r1 = apply(ip, env, code, r1, stack, sp, bindings)
            ip += 1
            sp -= 2
        elif op == OP_TRY:
            try:
                assert isinstance(r1, space.W_Fun)
                r1 = eval(env, bindings, bindings.st, r1.code)
                ip += code[ip + 1]
            except space.SpaceException as ex:
                stack[jit.promote(sp)] = space.wrap(ex.reason())
                sp += 1
                ip += 1
        else:
            raise Exception("Unknown code: %s, ip %s, code %s" %
                    (str(op), ip, str(code)))
        ip += 1
    assert sp == 0
    return r1
