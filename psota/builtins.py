import space
import eval
import os
from rpython.rlib import rfile

def arity(n):
    def wrap(f):
        def wrapped(self, args, *rest):
            if len(args) != n:
                raise space.ArityException(len(args), n)
            return f(self, args, *rest)
        return wrapped
    return wrap

class Print1(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        os.write(1, args[0].to_str())

class Eq(space.W_BIF):
    @arity(2)
    def invoke(self, args, *_):
        if args[0].equals(args[1]):
            return space.w_true
        else:
            return space.w_false

def int_binary_op(op):
    @arity(2)
    def f(self, args, *_):
        a = space.cast(args[0], space.W_Int)
        b = space.cast(args[1], space.W_Int)
        return space.W_Int(op(a.val, b.val))
    return f

class Mult(space.W_BIF):
    invoke = int_binary_op(lambda a, b: a * b)

class Add(space.W_BIF):
    invoke = int_binary_op(lambda a, b: a + b)

class Subtract(space.W_BIF):
    invoke = int_binary_op(lambda a, b: a - b)

class LT(space.W_BIF):
    @arity(2)
    def invoke(self, args, *_):
        a = space.cast(args[0], space.W_Int)
        b = space.cast(args[1], space.W_Int)
        return space.wrap(a.val < b.val)

class List(space.W_BIF):
    def invoke(self, args, *_):
        return space.wrap(args)

class Vector(space.W_BIF):
    def invoke(self, args, *_):
        return space.W_Vector(args)

class First(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        return args[0].first()

class Rest(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        return args[0].rest()

class Cons(space.W_BIF):
    @arity(2)
    def invoke(self, args, *_):
        head, tail = args
        if tail is space.w_nil:
            return space.W_List(args[0], space.w_empty_list)
        else:
            return space.W_List(args[0], args[1])

class Gensym(space.W_BIF):
    def __init__(self):
        self.counter = 0

    @arity(1)
    def invoke(self, args, ctx):
        val = args[0].to_str() + str(self.counter)
        ctx.st().add_sym(val)
        self.counter += 1
        return space.W_Sym(val)

class ArrayMap(space.W_BIF):
    def invoke(self, args, *_):
        return space.W_ArrayMap(args)

class HashMap(space.W_BIF):
    def invoke(self, args, *_):
        return space.W_HashMap(args)

class Get(space.W_BIF):
    def invoke(self, args, *_):
        argc = len(args)
        if argc not in [2, 3]:
            raise space.ArityException(len(args))
        map = args[0]
        if map == space.w_nil:
            return space.w_nil
        elif argc == 2:
            return args[0].get(args[1], space.w_nil)
        else:
            return args[0].get(args[1], args[2])

class Assoc(space.W_BIF):
    @arity(3)
    def invoke(self, args, *_):
        return args[0].assoc(args[1], args[2])

class Dissoc(space.W_BIF):
    @arity(2)
    def invoke(self, args, *_):
        return args[0].dissoc(args[1])

class Meta(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        return args[0].meta()

class WithMeta(space.W_BIF):
    @arity(2)
    def invoke(self, args, *_):
        return args[0].with_meta(args[1])

class AlterMeta(space.W_BIF):
    @arity(2)
    def invoke(self, args, ctx):
        w_var = space.cast(args[0], space.W_Var)
        w_fn = space.cast(args[1], space.W_Fun)
        w_meta = eval.invoke_fn(w_fn, [w_var.meta()], ctx)
        w_var.set_meta(w_meta)

class Var(space.W_BIF):
    @arity(1)
    def invoke(self, args, ctx):
        w_arg = space.cast(args[0], space.W_Sym)
        return ctx.bindings().get_var(w_arg.val)

class AlterVarRoot(space.W_BIF):
    @arity(2)
    def invoke(self, args, ctx):
        w_var = space.cast(args[0], space.W_Var)
        w_fn = space.cast(args[1], space.W_Fun)
        w_new = eval.invoke_fn(w_fn, [w_var.w_val], ctx)
        ctx.bindings().alter_var(w_var, w_new)
        return w_new

class Eval(space.W_BIF):
    @arity(1)
    def invoke(self, args, ctx):
        from compiler import emit
        w_form = args[0]
        code = emit(ctx, w_form)
        value = ctx.run(code)
        return value

class ReadString(space.W_BIF):
    @arity(1)
    def invoke(self, args, ctx):
        w_str = space.cast(args[0], space.W_String)
        from parser import parse
        parsed = parse(w_str.val)
        if len(parsed) == 0:
            raise space.ParsingException("EOF")
        return parsed[0]

class Class(space.W_BIF):
    @arity(1)
    def invoke(self, args, ctx):
        return args[0].type()

class LazySeq(space.W_BIF):
    @arity(1)
    def invoke(self, args, ctx):
        w_fn = space.cast(args[0], space.W_Fun)
        pr = LazySeq.Promise(w_fn, ctx)
        return space.W_LazySeq(pr)

    class Promise:
        def __init__(self, w_fn, ctx):
            self.w_fn = w_fn
            self.ctx = ctx

        def deliver(self):
            return eval.invoke_fn(self.w_fn, [], self.ctx)

def type_predicate(type):
    @arity(1)
    def f(self, args, *_):
        arg = args[0]
        return space.wrap(isinstance(arg, type))
    return f

class SymbolP(space.W_BIF):
    invoke = type_predicate(space.W_Sym)

class KeywordP(space.W_BIF):
    invoke = type_predicate(space.W_Keyword)

class VectorP(space.W_BIF):
    invoke = type_predicate(space.W_Vector)

class MapP(space.W_BIF):
    invoke = type_predicate(space.W_Map)

class ListP(space.W_BIF):
    invoke = type_predicate(space.W_List)

class Deref(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        w_val = args[0]
        return w_val.deref()

class Atom(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        w_val = args[0]
        return space.W_Atom(w_val)

class SwapBang(space.W_BIF):
    @arity(2)
    def invoke(self, args, ctx):
        w_atom = space.cast(args[0], space.W_Atom)
        w_fn = space.cast(args[1], space.W_Fun)
        w_new = eval.invoke_fn(w_fn, [w_atom.deref()], ctx)
        w_atom.reset(w_new)
        return w_new

class _LazyFile:
    def __init__(self, name):
        self.stdin = None
        self.name = name

    def get(self):
        if self.stdin is None:
            self.stdin = rfile.create_file(self.name)
        return self.stdin

stdin = _LazyFile("/dev/stdin")

class Getline(space.W_BIF):
    @arity(0)
    def invoke(self, *_):
        return space.wrap(str(stdin.get().readline()))

class Keyword(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        w_obj = args[0]
        if isinstance(w_obj, space.W_String):
            return space.W_Keyword(w_obj.val)
        return space.w_nil

class Str(space.W_BIF):
    def invoke(self, args, *_):
        acc = ""
        for w_arg in args:
            if isinstance(w_arg, space.W_String):
                acc += w_arg.val
            else:
                acc += w_arg.to_str()
        return space.wrap(acc)

class Hash(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        return space.W_Int(args[0].hash())

class Throw(space.W_BIF):
    @arity(1)
    def invoke(self, args, *_):
        w_obj = space.cast(args[0], space.W_String)
        raise space.SpaceException(w_obj.val)

class InNs(space.W_BIF):
    @arity(1)
    def invoke(self, args, ctx):
        w_obj = space.cast(args[0], space.W_Sym)
        ctx.bindings().set_ns(w_obj.val)

class Load(space.W_BIF):
    @arity(1)
    def invoke(self, args, ctx):
        from parser import parse
        from compiler import emit
        w_str = space.cast(args[0], space.W_String)
        f = open(w_str.val)
        try:
            input = f.read()
            parsed = parse(input)
            for sexp in parsed:
                code = emit(ctx, sexp)
                ctx.run(code)
        finally:
            f.close()

class Macroexpand1(space.W_BIF):
    @arity(1)
    def invoke(self, args, ctx):
        form = args[0]
        if not isinstance(form, space.W_List):
            return form
        head = form.first()
        if not isinstance(head, space.W_Sym):
            return form
        st = ctx.st()
        val = head.val
        if not st.has_macro(val):
            return form
        macro_fn = st.get_fn(st.get_macro(val))
        return eval.invoke_fn(macro_fn, space.unwrap(form.rest()), ctx)

consts = [
    ('nil', space.w_nil),
    ('false', space.w_false),
    ('true', space.w_true),
    ]

core = [
        ('*', Mult()),
        ('=', Eq()),
        ('+', Add()),
        ('-', Subtract()),
        ('<', LT()),
        ('print1', Print1()),
        ('list', List()),
        ('first', First()),
        ('rest', Rest()),
        ('cons', Cons()),
        ('vector', Vector()),
        ('gensym*', Gensym()),
        ('array-map', ArrayMap()),
        ('hash-map', HashMap()),
        ('get', Get()),
        ('assoc', Assoc()),
        ('dissoc', Dissoc()),
        ('meta', Meta()),
        ('with-meta', WithMeta()),
        ('alter-meta!', AlterMeta()),
        ('var*', Var()),
        ('alter-var-root', AlterVarRoot()),
        ('eval', Eval()),
        ('read-string', ReadString()),
        ('lazy-seq*', LazySeq()),
        ('class', Class()),
        ('symbol?', SymbolP()),
        ('keyword?', KeywordP()),
        ('vector?', VectorP()),
        ('map?', MapP()),
        ('list?', ListP()),
        ('deref', Deref()),
        ('atom', Atom()),
        ('swap!', SwapBang()),
        ('getline', Getline()),
        ('keyword', Keyword()),
        ('str', Str()),
        ('hash', Hash()),
        ('throw', Throw()),
        ('in-ns', InNs()),
        ('load', Load()),
        ('macroexpand-1', Macroexpand1()),
        ]
