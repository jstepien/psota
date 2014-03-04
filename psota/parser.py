from rpython.rlib.parsing.pypackrat import PackratParser
from rpython.rlib.parsing.makepackrat import BacktrackException, Status

from space import (W_Int, W_Sym, W_Vector, wrap, W_ArrayMap, W_Keyword,
        W_Char, ParsingException)

# Most of the parser has been taken from lang-scheme. You can find it at
# https://bitbucket.org/pypy/lang-scheme/src/b1d5a1b8744f/scheme/ssparser.py

def str_unquote(s):
    str_lst = []
    pos = 1
    last = len(s)-1
    while pos < last:
        ch = s[pos]
        if ch == '\\':
            pos += 1
            ch = s[pos]
            if ch == '\\' or ch == '\"':
                str_lst.append(ch)
            elif ch == 'n':
                str_lst.append("\n")
            else:
                raise Exception("syntax error: " + s)
        else:
            str_lst.append(ch)
        pos += 1
    return ''.join(str_lst)

class QuoppaParser(PackratParser):
    r"""
    SYMBOL:
        c = `[\+\-\*\^\?a-zA-Z!<=>_~/$%&:][\+\-\*\^\?a-zA-Z0-9!<=>_~/$%&:.]*`
        IGNORE*
        return {W_Sym(c)};

    keyword:
        `:`
        c = `[\+\-\*\^\?a-zA-Z!<=>_/$%&:][\+\-\*\^\?a-zA-Z0-9!<=>_~/$%&:.]*`
        IGNORE*
        return {W_Keyword(c)};

    FIXNUM:
        c = `\-?(0|([1-9][0-9]*))`
        IGNORE*
        return {W_Int(int(c))};

    IGNORE:
        ` |,|\n|\t|;[^\n]*`;

    STRING:
        c = `\"([^\\\"]|\\\"|\\\\|\\n)*\"`
        IGNORE*
        return {wrap(str_unquote(c))};

    CHAR:
        '\'
        c = `[^ \n\t][a-z]*`
        IGNORE*
        return {char(c)};

    EOF:
        !__any__;

    file:
        IGNORE*
        s = sexpr*
        EOF
        return {s};

    quote:
       `'`
       s = sexpr
       return {quote(s)};

    quasiquote:
       `\``
       s = sexpr
       return {quasiquote(s)};

    unquote:
       `~`
       s = sexpr
       return {unquote(s)};

    sexpr:
        list
      | vector
      | map
      | quote
      | quasiquote
      | unquote
      | FIXNUM
      | keyword
      | STRING
      | CHAR
      | SYMBOL;

    vector:
        '['
        IGNORE*
        s = sexpr*
        ']'
        IGNORE*
        return {W_Vector(s)};

    list:
        '('
        IGNORE*
        s = sexpr*
        ')'
        IGNORE*
        return {wrap(s)};

    map:
        '{'
        IGNORE*
        s = sexpr*
        '}'
        IGNORE*
        return {map(s)};
    """

def parse(code):
    try:
        p = QuoppaParser(code)
        return p.file()
    except Exception as ex:
        raise ParsingException(str(ex))

def quote(sexpr):
    return wrap([W_Sym('quote'), sexpr])

def quasiquote(sexpr):
    return wrap([W_Sym('`'), sexpr])

def unquote(sexpr):
    return wrap([W_Sym('~'), sexpr])

def map(args):
    return W_ArrayMap(args)

def char(val):
    if len(val) == 1:
        return W_Char(ord(val[0]))
    elif val == "space":
        return W_Char(ord(" "))
    elif val == "newline":
        return W_Char(ord("\n"))
    else:
        raise ParsingException("Invalid character: %s" % val)
