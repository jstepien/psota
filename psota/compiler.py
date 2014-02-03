import eval
from eval import (OP_KEYWORD, OP_IF, OP_SYM, OP_QUOTE, OP_RELJMP, OP_PUSH, OP_FN,
        OP_RECUR, OP_INVOKE, OP_DEF, OP_INT, OP_PUSH_ENV, OP_POP_ENV, OP_APPLY,
        OP_STRING, OP_TRY, OP_CHAR)
from space import (W_List, W_Int, W_EmptyList, W_Vector, W_Sym, W_Fun, unwrap,
        W_Seq, W_ArrayMap, W_Keyword, w_nil, W_String, CompilationException,
        W_Char, cast)

def mkfn(st, bindings, w_args, w_body):
    args = []
    rest_args_id = -1
    arg_vec_w = unwrap(cast(w_args, W_Seq))
    idx = 0
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
    code = emit(st, bindings, w_body, recur_bindings)
    return st.add_fn(W_Fun(code, ids, rest_args_id))

def defmacro(st, bindings, list_w):
    _, w_name, w_args, w_body = list_w
    fn_id = mkfn(st, bindings, w_args, w_body)
    st.add_macro(cast(w_name, W_Sym).val, fn_id)
    return []

def expand_macro(st, bindings, macro_id, args_w, recur_bindings):
    args_code = []
    for w_arg in args_w:
        args_code += emit_quote(st, bindings, w_arg) + [OP_PUSH]
    expanding_code = [OP_FN, macro_id, OP_INVOKE, len(args_w)]
    all_code = args_code + expanding_code
    value = eval.eval(eval.base_env(st), bindings, st, all_code)
    return emit(st, bindings, value, recur_bindings)

def fn(st, bindings, list_w):
    _, w_args, w_body = list_w
    fn_id = mkfn(st, bindings, w_args, w_body)
    return [OP_FN, fn_id]

def try_block(st, bindings, list_w):
    _, w_body, w_catch = list_w
    fn_code = fn(st, bindings, unwrap(w_body))
    catch_code = fn(st, bindings, unwrap(w_catch))
    return fn_code + [OP_TRY, 3 + len(catch_code)] + catch_code + [OP_INVOKE, 1]

def somehow_quoted_emit(list_handling_fn):
    def f(st, bindings, w_val):
        if isinstance(w_val, W_Sym):
            id = st.add_sym(w_val.val)
            return [OP_QUOTE, id]
        elif isinstance(w_val, W_Keyword):
            id = st.add_sym(w_val.val)
            return [OP_KEYWORD, id]
        elif isinstance(w_val, W_String):
            id = st.add_sym(w_val.val)
            return [OP_STRING, id]
        elif isinstance(w_val, W_Int):
            return [OP_INT, w_val.val]
        elif isinstance(w_val, W_List):
            return list_handling_fn(st, bindings, w_val, f)
        elif isinstance(w_val, W_Vector):
            code = []
            for w_elem in w_val.elems():
                code += f(st, bindings, w_elem) + [OP_PUSH]
            return code + [OP_SYM, st.add_sym("vector"),
                    OP_INVOKE, len(w_val.elems())]
        elif isinstance(w_val, W_ArrayMap):
            code = []
            for w_elem in w_val.elems():
                code += f(st, bindings, w_elem) + [OP_PUSH]
            return code + [OP_SYM, st.add_sym("array-map"),
                    OP_INVOKE, len(w_val.elems())]
        elif w_val == w_nil:
            return [OP_SYM, st.get_sym_id("nil")]
        else:
            raise Exception("how do i quasiquote? %s" % w_val)
    return f

def is_unquote(list_w):
    if len(list_w) != 2:
        return False
    w_first = list_w[0]
    return isinstance(w_first, W_Sym) and w_first.to_str() == '~'

def emit_quasiquoted_list(st, bindings, w_val, recur):
    list_w = unwrap(w_val)
    if is_unquote(list_w):
        code = emit(st, bindings, list_w[1])
        return code
    else:
        code = []
        list = unwrap(w_val)
        for w_elem in list:
            code += recur(st, bindings, w_elem) + [OP_PUSH]
        return code + [OP_SYM, st.add_sym("list"), OP_INVOKE, len(list)]

emit_quasiquote = somehow_quoted_emit(emit_quasiquoted_list)

def emit_quoted_list(st, bindings, w_val, recur):
    code = []
    list = unwrap(w_val)
    for w_elem in list:
        code += recur(st, bindings, w_elem) + [OP_PUSH]
    return code + [OP_SYM, st.add_sym("list"), OP_INVOKE, len(list)]

emit_quote = somehow_quoted_emit(emit_quoted_list)

def emit_list(st, bindings, node, recur_bindings):
    list_w = unwrap(node)
    if len(list_w) == 0:
        return [OP_SYM, st.add_sym("list"), OP_INVOKE, 0]
    w_head = list_w[0]
    args_w = list_w[1:]
    if isinstance(w_head, W_Sym):
        head = w_head.val
        if head == "if":
            cond_code = emit(st, bindings, list_w[1])
            true_code = emit(st, bindings, list_w[2], recur_bindings)
            false_code = emit(st, bindings, list_w[3], recur_bindings)
            jmp_code = [OP_RELJMP, len(false_code)]
            code = (cond_code + [OP_IF, len(true_code) + len(jmp_code)] +
                    true_code + jmp_code + false_code)
            return code
        elif head == "let*":
            sym = cast(list_w[1], W_Sym)
            binding_code = emit(st, bindings, list_w[2])
            id = st.add_sym(sym.val)
            inner_code = emit(st, bindings, list_w[3], recur_bindings)
            code = binding_code + [OP_PUSH_ENV, id] + inner_code + [OP_POP_ENV]
            return code
        elif head == "do":
            body_code = []
            for step in list_w[1:]:
                body_code += emit(st, bindings, step, recur_bindings)
            return body_code
        elif head == "quote":
            return emit_quote(st, bindings, list_w[1])
        elif head == "`":
            return emit_quasiquote(st, bindings, list_w[1])
        elif head == "fn*":
            return fn(st, bindings, list_w)
        elif head == "defmacro*":
            return defmacro(st, bindings, list_w)
        elif head == "def*":
            var_sym = cast(list_w[1], W_Sym)
            id = st.add_sym(var_sym.val)
            val_code = emit(st, bindings, list_w[2])
            return val_code + [OP_DEF, id]
        elif head == "try*":
            return try_block(st, bindings, list_w)
        elif head == "recur":
            args = list_w[1:]
            args_code = []
            for arg in args:
                c = emit(st, bindings, arg)
                args_code += c + [OP_PUSH]
            if recur_bindings == no_recur_bindings:
                raise CompilationException("Not a recur point :o")
            (ids, rest_id) = recur_bindings
            bindings_ids = [x for x in reversed(ids)] + \
                    [-rest_id if rest_id >= 0 else -1]
            return args_code + [OP_RECUR, len(args)] + bindings_ids
        elif st.has_macro(head):
            return expand_macro(st, bindings, st.get_macro(head), list_w[1:], recur_bindings)
        elif head == "apply":
            args_code = []
            for arg in args_w:
                c = emit(st, bindings, arg)
                args_code += c + [OP_PUSH]
            return args_code + [OP_APPLY, len(args_w)]
    args_code = []
    for arg in args_w:
        c = emit(st, bindings, arg)
        args_code += c + [OP_PUSH]
    fn_code = emit(st, bindings, w_head)
    return args_code + fn_code + [OP_INVOKE, len(args_w)]

no_recur_bindings = ([], -1)
empty_recur_bindings = ([], -2)

def emit(st, bindings, node, recur_bindings=no_recur_bindings):
    if isinstance(node, W_Sym):
        sym = node.val
        if sym == "~":
            raise Exception("Shouldn't see '~' here!")
        if not sym in st.syms:
            raise CompilationException("Undefined symbol: %s" % str(sym))
        return [OP_SYM, st.get_sym_id(sym)]
    elif isinstance(node, W_Keyword):
        sym = node.val
        id = st.add_sym(sym)
        return [OP_KEYWORD, id]
    elif isinstance(node, W_String):
        id = st.add_sym(node.val)
        return [OP_STRING, id]
    elif isinstance(node, W_Int):
        return [OP_INT, node.val]
    elif isinstance(node, W_Char):
        return [OP_CHAR, node.val]
    elif isinstance(node, W_List):
        return emit_list(st, bindings, node, recur_bindings)
    elif isinstance(node, W_Vector):
        code = []
        for w_elem in node.elems():
            code += emit(st, bindings, w_elem) + [OP_PUSH]
        return code + [OP_SYM, st.add_sym("vector"), OP_INVOKE, len(node.elems())]
    elif isinstance(node, W_ArrayMap):
        code = []
        for w_elem in node.elems():
            code += emit(st, bindings, w_elem) + [OP_PUSH]
        return code + [OP_SYM, st.add_sym("array-map"), OP_INVOKE, len(node.elems())]
    elif node == w_nil:
        return [OP_SYM, st.get_sym_id("nil")]
    else:
        raise Exception("How to emit? %s" % node)
