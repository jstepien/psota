import eval
import sys
import parser
import compiler
import builtins

def entry_point(argv):
    if len(argv) == 1:
        filename = "repl.clj"
    else:
        filename = argv[1]
    f = open(filename)
    input = f.read()
    f.close()
    parsed = parser.parse(input)
    ctx = eval.Context()
    for sexp in parsed:
        code = compiler.emit(ctx, eval.read(ctx, sexp))
        ctx.run(code)
    return 0

def target(driver, args):
    return entry_point, None

def jitpolicy(driver):
    from rpython.jit.codewriter.policy import JitPolicy
    return JitPolicy()

if __name__ == "__main__":
    entry_point(sys.argv)
