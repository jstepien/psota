from rpython.rlib import jit

import space
import builtins
import ops
from symbol_table import SymbolTable
from bindings import Bindings

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

class Context:
    def __init__(self, st=None, bindings=None):
        if st is None:
            self._st = SymbolTable()
        else:
            self._st = st
        if bindings is None:
            self._bindings = Bindings(self._st)
        else:
            self._bindings = bindings

    def st(self):
        return self._st

    def bindings(self):
        return self._bindings

    def run(self, code):
        return eval(base_env(self._st), self._bindings, self._st, code)

ops_names = {
        ops.KEYWORD: 'KEYWORD',
        ops.IF: 'IF',
        ops.PUSH_ENV: 'PUSH_ENV',
        ops.POP_ENV: 'POP_ENV',
        ops.SYM: 'SYM',
        ops.INT: 'INT',
        ops.QUOTE: 'QUOTE',
        ops.RELJMP: 'RELJMP',
        ops.FN: 'FN',
        ops.INVOKE: 'INVOKE',
        ops.DEF: 'DEF',
        ops.PUSH: 'PUSH',
        ops.APPLY: 'APPLY',
        ops.RECUR: 'RECUR',
        ops.STRING: 'STRING',
        ops.TRY: 'TRY',
        }

def get_location(ip, code):
    def code_to_str(code):
        val = ""
        for op in code:
            if op in ops_names:
                val += ops_names[op]
            else:
                val += str(op)
            val += " "
        return val
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
    if isinstance(fn, space.W_Fun):
        arg_ids_len = const_len(fn.arg_ids)
        if fn.env.on_stack:
            new_env = Env([], fn.env)
        else:
            new_env = fn.env
        try:
            new_env.mark_used()
            if (argc < arg_ids_len or
                    (argc > arg_ids_len and not fn.got_rest_args())):
                raise space.ArityException(argc, arg_ids_len)
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
        new_sp = sp - argc
        assert new_sp >= 0
        args = [space.w_nil for _ in range(argc)]
        for i in range(new_sp, sp):
            args[i - new_sp] = stack[i]
        ret = fn.invoke(args, bindings)
        if ret is None:
            ret = space.w_nil
        return ret

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
    if isinstance(fn, space.W_Fun):
        arg_ids_len = len(fn.arg_ids)
        if fn.env.on_stack:
            new_env = Env([], fn.env)
        else:
            new_env = fn.env
        try:
            new_env.mark_used()
            if (argc < arg_ids_len or
                    (argc > arg_ids_len and not fn.got_rest_args())):
                raise space.ArityException(argc, arg_ids_len)
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
        ret = fn.invoke(args, bindings)
        if ret is None:
            ret = space.w_nil
        return ret

@jit.elidable
def get_op(code, ip):
    return code[ip]

@jit.elidable
def const_len(code):
    return len(code)

stack_size = 100
empty_stack = []

def eval(env, bindings, st, code):
    ip = 0
    stack = empty_stack
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
        if op == ops.IF:
            ip += 1
            if not is_true(r1):
                ip += get_op(code, ip)
        elif op == ops.SYM:
            ip += 1
            r1 = lookup(env, jit.promote(bindings), get_op(code, ip))
        elif op == ops.KEYWORD:
            ip += 1
            r1 = space.W_Keyword(st.get_sym(get_op(code, ip)))
        elif op == ops.STRING:
            ip += 1
            r1 = space.W_String(st.get_sym(get_op(code, ip)))
        elif op == ops.INT:
            ip += 1
            r1 = space.W_Int(get_op(code, ip))
        elif op == ops.PUSH_ENV:
            ip += 1
            env = Env([(get_op(code, ip), r1)], env)
        elif op == ops.POP_ENV:
            env = env.parent
        elif op == ops.QUOTE:
            ip += 1
            r1 = space.W_Sym(st.get_sym(get_op(code, ip)))
        elif op == ops.RELJMP:
            ip += get_op(code, ip + 1) + 1
        elif op == ops.FN:
            ip += 1
            r1 = st.get_fn(get_op(code, ip)).with_env(env)
        elif op == ops.PUSH:
            if stack is empty_stack:
                stack = [None for _ in range(stack_size)]
            stack[jit.promote(sp)] = r1
            sp += 1
        elif op == ops.DEF:
            ip += 1
            bindings.set(get_op(code, ip), r1)
        elif op == ops.RECUR:
            ip += 1
            argc = jit.promote(get_op(code, ip))
            sp -= argc
            idx = argc - 1
            while idx >= 0:
                ip += 1
                env.set(get_op(code, ip), stack[jit.promote(idx + sp)])
                idx -= 1
            ip = -1
        elif op == ops.INVOKE:
            r1 = invoke(ip, env, code, r1, stack, sp, bindings)
            ip += 1
            sp -= get_op(code, ip)
        elif op == ops.APPLY:
            r1 = apply(ip, env, code, r1, stack, sp, bindings)
            ip += 1
            sp -= 2
        elif op == ops.TRY:
            try:
                assert isinstance(r1, space.W_Fun)
                r1 = eval(env, bindings, bindings.st, r1.code)
                ip += code[ip + 1]
            except space.SpaceException as ex:
                if stack is empty_stack:
                    stack = [None for _ in range(stack_size)]
                stack[jit.promote(sp)] = space.wrap(ex.reason())
                sp += 1
                ip += 1
        elif op == ops.CHAR:
            ip += 1
            r1 = space.W_Char(get_op(code, ip))
        else:
            raise Exception("Unknown code: %s, ip %s, code %s" %
                    (str(op), ip, str(code)))
        ip += 1
    assert sp == 0
    return r1
