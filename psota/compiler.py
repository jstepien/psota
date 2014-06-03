import ops
from space import (W_List, W_Int, W_EmptyList, W_Vector, W_Sym, W_Fun, unwrap,
        W_Seq, W_ArrayMap, W_Keyword, w_nil, W_String, CompilationException,
        W_Char, cast)

def mkfn(ctx, w_args, body_w):
    args = []
    rest_args_id = -1
    arg_vec_w = unwrap(cast(w_args, W_Seq))
    idx = 0
    st = ctx.st()
    while idx < len(arg_vec_w):
        w_arg = cast(arg_vec_w[idx], W_Sym)
        if w_arg.val == '&':
            assert idx == len(arg_vec_w) - 2
            w_last = cast(arg_vec_w[idx + 1], W_Sym)
            rest_args_id = st.add_sym(w_last.val)
            break
        else:
            args.append(w_arg.val)
        idx += 1
    ids = []
    for arg in args:
        id = st.add_sym(arg)
        ids.append(id)
    if len(ids) > 0 or rest_args_id >= 0:
        recur_bindings = (ids, rest_args_id)
    else:
        recur_bindings = empty_recur_bindings
    code = []
    for w_elem in body_w:
        code += emit(ctx, w_elem, recur_bindings)
    return st.add_fn(W_Fun(code, ids, rest_args_id))

def defmacro(ctx, list_w):
    _, w_name, w_args = list_w[0:3]
    fn_id = mkfn(ctx, w_args, list_w[3:])
    ctx.st().add_macro(cast(w_name, W_Sym).val, fn_id)
    return []

def expand_macro(ctx, macro_id, args_w, recur_bindings):
    args_code = []
    for w_arg in args_w:
        args_code += emit_quote(ctx, w_arg) + [ops.PUSH]
    expanding_code = [ops.FN, macro_id, ops.INVOKE, len(args_w)]
    all_code = args_code + expanding_code
    value = ctx.run(all_code)
    return emit(ctx, value, recur_bindings)

def fn(ctx, list_w):
    _, w_args = list_w[0:2]
    fn_id = mkfn(ctx, w_args, list_w[2:])
    return [ops.FN, fn_id]

def try_block(ctx, list_w):
    _, w_body, w_catch, w_finally = list_w
    fn_code = fn(ctx, unwrap(w_body))
    if w_catch is w_nil:
        catch_code = []
    else:
        catch_code = fn(ctx, unwrap(w_catch)) + [ops.INVOKE, 1]
    finally_id = fn(ctx, unwrap(w_finally))[1] if w_finally is not w_nil else -1
    return fn_code + [ops.TRY, finally_id, 1 + len(catch_code)] + catch_code

def somehow_quoted_emit(list_handling_fn):
    def f(ctx, w_val):
        st = ctx.st()
        if isinstance(w_val, W_Sym):
            id = st.add_sym(w_val.val)
            return [ops.QUOTE, id]
        elif isinstance(w_val, W_Keyword):
            id = st.add_sym(w_val.val)
            return [ops.KEYWORD, id]
        elif isinstance(w_val, W_String):
            id = st.add_sym(w_val.val)
            return [ops.STRING, id]
        elif isinstance(w_val, W_Int):
            return [ops.INT, w_val.val]
        elif isinstance(w_val, W_Char):
            return [ops.CHAR, w_val.val]
        elif isinstance(w_val, W_List):
            return list_handling_fn(ctx, w_val, f)
        elif isinstance(w_val, W_Vector):
            code = []
            for w_elem in w_val.elems():
                code += f(ctx, w_elem) + [ops.PUSH]
            return code + [ops.SYM, st.add_sym("vector"),
                    ops.INVOKE, len(w_val.elems())]
        elif isinstance(w_val, W_ArrayMap):
            code = []
            for w_elem in w_val.elems():
                code += f(ctx, w_elem) + [ops.PUSH]
            return code + [ops.SYM, st.add_sym("array-map"),
                    ops.INVOKE, len(w_val.elems())]
        elif w_val == w_nil:
            return [ops.SYM, st.get_sym_id("nil")]
        else:
            raise Exception("how do i quasiquote? %s" % w_val)
    return f

def is_unquote(list_w):
    if len(list_w) != 2:
        return False
    w_first = list_w[0]
    return isinstance(w_first, W_Sym) and w_first.to_str() == '~'

def emit_quasiquoted_list(ctx, w_val, recur):
    list_w = unwrap(w_val)
    if is_unquote(list_w):
        code = emit(ctx, list_w[1])
        return code
    else:
        code = []
        list = unwrap(w_val)
        for w_elem in list:
            code += recur(ctx, w_elem) + [ops.PUSH]
        return code + [ops.SYM, ctx.st().add_sym("list"), ops.INVOKE, len(list)]

emit_quasiquote = somehow_quoted_emit(emit_quasiquoted_list)

def emit_quoted_list(ctx, w_val, recur):
    code = []
    list = unwrap(w_val)
    for w_elem in list:
        code += recur(ctx, w_elem) + [ops.PUSH]
    return code + [ops.SYM, ctx.st().add_sym("list"), ops.INVOKE, len(list)]

emit_quote = somehow_quoted_emit(emit_quoted_list)

def emit_list(ctx, node, recur_bindings):
    st = ctx.st()
    list_w = unwrap(node)
    if len(list_w) == 0:
        return [ops.SYM, st.add_sym("list"), ops.INVOKE, 0]
    w_head = list_w[0]
    args_w = list_w[1:]
    if isinstance(w_head, W_Sym):
        head = w_head.val
        if head == "if":
            cond_code = emit(ctx, list_w[1])
            true_code = emit(ctx, list_w[2], recur_bindings)
            false_code = emit(ctx, list_w[3], recur_bindings)
            jmp_code = [ops.RELJMP, len(false_code)]
            code = (cond_code + [ops.IF, len(true_code) + len(jmp_code)] +
                    true_code + jmp_code + false_code)
            return code
        elif head == "let*":
            sym = cast(list_w[1], W_Sym)
            binding_code = emit(ctx, list_w[2])
            id = st.add_sym(sym.val)
            inner_code = emit(ctx, list_w[3], recur_bindings)
            code = binding_code + [ops.PUSH_ENV, id] + inner_code + [ops.POP_ENV]
            return code
        elif head == "do":
            body_code = []
            for step in list_w[1:]:
                body_code += emit(ctx, step, recur_bindings)
            return body_code
        elif head == "quote":
            return emit_quote(ctx, list_w[1])
        elif head == "qquote*":
            return emit_quasiquote(ctx, list_w[1])
        elif head == "fn*":
            return fn(ctx, list_w)
        elif head == "defmacro*":
            return defmacro(ctx, list_w)
        elif head == "def*":
            var_sym = cast(list_w[1], W_Sym)
            id = st.add_sym(var_sym.val)
            val_code = emit(ctx, list_w[2])
            return val_code + [ops.DEF, id]
        elif head == "try*":
            return try_block(ctx, list_w)
        elif head == "recur":
            args = list_w[1:]
            args_code = []
            (ids, rest_id) = recur_bindings
            if len(args) < len(ids):
                msg = "Invalid number of recur arguments: %s given, %s expected"
                raise CompilationException(msg % (len(args), len(ids)))
            for arg in args:
                c = emit(ctx, arg)
                args_code += c + [ops.PUSH]
            if recur_bindings == no_recur_bindings:
                raise CompilationException("Not a recur point :o")
            bindings_ids = [x for x in reversed(ids)] + \
                    [rest_id if rest_id >= 0 else -1]
            return args_code + [ops.RECUR, len(args)] + bindings_ids
        elif st.has_macro(head):
            return expand_macro(ctx, st.get_macro(head), list_w[1:], recur_bindings)
        elif head == "apply":
            args_code = []
            for arg in args_w:
                c = emit(ctx, arg)
                args_code += c + [ops.PUSH]
            return args_code + [ops.APPLY, len(args_w)]
    args_code = []
    for arg in args_w:
        c = emit(ctx, arg)
        args_code += c + [ops.PUSH]
    fn_code = emit(ctx, w_head)
    return args_code + fn_code + [ops.INVOKE, len(args_w)]

no_recur_bindings = ([], -1)
empty_recur_bindings = ([], -2)

def emit(ctx, node, recur_bindings=no_recur_bindings):
    st = ctx.st()
    if isinstance(node, W_Sym):
        sym = node.val
        if sym == "~":
            raise Exception("Shouldn't see '~' here!")
        return [ops.SYM, st.add_sym(sym)]
    elif isinstance(node, W_Keyword):
        sym = node.val
        id = st.add_sym(sym)
        return [ops.KEYWORD, id]
    elif isinstance(node, W_String):
        id = st.add_sym(node.val)
        return [ops.STRING, id]
    elif isinstance(node, W_Int):
        return [ops.INT, node.val]
    elif isinstance(node, W_Char):
        return [ops.CHAR, node.val]
    elif isinstance(node, W_List):
        return emit_list(ctx, node, recur_bindings)
    elif isinstance(node, W_Vector):
        code = []
        for w_elem in node.elems():
            code += emit(ctx, w_elem) + [ops.PUSH]
        return code + [ops.SYM, st.add_sym("vector"), ops.INVOKE, len(node.elems())]
    elif isinstance(node, W_ArrayMap):
        code = []
        for w_elem in node.elems():
            code += emit(ctx, w_elem) + [ops.PUSH]
        return code + [ops.SYM, st.add_sym("array-map"), ops.INVOKE, len(node.elems())]
    elif node == w_nil:
        return [ops.SYM, st.get_sym_id("nil")]
    else:
        raise Exception("How to emit? %s" % node)
