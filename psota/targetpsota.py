import eval
import sys
import parser
import compiler
import symbol_table
import builtins

def entry_point(argv):
    f = open(argv[1])
    input = f.read()
    f.close()
    parsed = parser.parse(input)
    st = symbol_table.SymbolTable()
    bindings = eval.Bindings(st)
    value = None
    for sexp in parsed:
        code = compiler.emit(st, bindings, sexp)
        value = eval.eval(eval.base_env(st), bindings, st, code)
    return 0

def target(driver, args):
    return entry_point, None

def jitpolicy(driver):
    from rpython.jit.codewriter.policy import JitPolicy
    return JitPolicy()

if __name__ == "__main__":
    entry_point(sys.argv)
