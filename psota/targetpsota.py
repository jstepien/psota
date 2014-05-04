import eval
import sys
import parser
import compiler
import builtins

def entry_point(argv):
    f = open(argv[1])
    input = f.read()
    f.close()
    parsed = parser.parse(input)
    ctx = eval.Context()
    value = None
    for sexp in parsed:
        code = compiler.emit(ctx, sexp)
        value = ctx.run(code)
    return 0

def target(driver, args):
    return entry_point, None

def jitpolicy(driver):
    from rpython.jit.codewriter.policy import JitPolicy
    return JitPolicy()

if __name__ == "__main__":
    entry_point(sys.argv)
