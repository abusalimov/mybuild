"""
PLY-based parser for Myfile grammar.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from _compat import *

import ast
import functools
import ply.yacc

from mylang import lex
from mylang.location import Fileinfo
from mylang.location import Location

from util.itertools import send_next_iter
from util.operator import getter


# Location tracking.

def node_loc(ast_node, p):
    return Location.from_ast_node(ast_node, p.lexer.fileinfo)

def ploc(p, i):
    return Location(p.lexer.fileinfo, p.lineno(i), p.lexpos(i))

def pwloc(p, i):
    return p[i], ploc(p, i)

copy_loc = ast.copy_location

def set_loc(ast_node, loc):
    return loc.init_ast_node(ast_node)


# Here go some utils.

def to_rlist(reversed_list):
    return reversed_list[::-1]


class MySyntaxError(Exception):
    """Stub class for using instead of standard SyntaxError because the latter
    has the special meaning for PLY."""

    def __init__(self, msg, loc=None):
        loc_args = (loc.to_syntax_error_tuple(),) if loc is not None else ()
        super(MySyntaxError, self).__init__(msg, *loc_args)


def fold_trailers(expr, trailers_wloc):
    for trailer, loc in reversed(trailers_wloc):
        expr = loc.init_ast_node(trailer(expr))

    return expr

def ast_self(ctx=None):
    if ctx is None:
        ctx = ast.Load()
    return ast.Name('self', ctx)


# Grammar definitions for PLY.

tokens = lex.tokens


def p_exec_start(p):
    """exec_start : stmts"""
    p[0] = ast.Module(body=to_rlist(p[1]))

def p_eval_start(p):
    """eval_start : test"""
    p[0] = ast.Expression(body=p[1])


def p_stmt(p):
    """stmt : bindings SEMI"""
    bindings, value = p[1]
    if bindings:
        p[0] = ast.Assign(to_rlist(bindings), value)
    else:
        p[0] = ast.Expr(value)


def p_bindings_value(p):
    """bindings : test"""
    p[0] = [], p[1]

def p_bindings_targets(p):
    """bindings : ID DOUBLECOLON bindings"""
    l, value = p[0] = p[3]
    l.append(ast.Name(p[1], ast.Store()))

    # the following dirty hack is to provide an access to binding names
    # in runtime

    call = value
    if not isinstance(call, ast.Call):
        return

    name = call.func
    if not (isinstance(name, ast.Name) and
            name.id == '__my_setter__'):
        return

    call.args.append(ast.Str(p[1]))


def p_testlist_empty(p):
    """testlist :"""
    p[0] = [], None

def p_testlist_single(p):
    """testlist : test"""
    el = p[1]
    p[0] = [el], el

def p_testlist_list(p):
    """testlist : test COMMA testlist"""
    l, _ = p[3]
    l.append(p[1])
    p[0] = l, None


def p_test(p):
    "test : atom trailers"""
    p[0] = fold_trailers(p[1], p[2])


def p_atom_name(p):
    """atom : ID"""
    p[0] = set_loc(ast.Name(p[1], ast.Load()), ploc(p, 1))

def p_atom_num(p):
    """atom : NUMBER"""
    p[0] = set_loc(ast.Num(p[1]), ploc(p, 1))

def p_atom_str(p):
    """atom : STRING"""
    p[0] = set_loc(ast.Str(p[1]), ploc(p, 1))

def p_atom_list(p):
    """atom : LBRACKET testlist RBRACKET"""
    p[0] = set_loc(ast.List(to_rlist(p[2][0]), ast.Load()), ploc(p, 1))

def p_atom_dict(p):
    """atom : LBRACE dictentlist RBRACE"""
    keys   = list(map(getter[0], p[2]))
    values = list(map(getter[1], p[2]))

    p[0] = set_loc(ast.Dict(keys, values), ploc(p, 1))

def p_dictent(p):
    """dictent : test COLON test"""
    p[0] = (p[1], p[3])

def p_atom_tuple(p):
    """atom : LPAREN testlist RPAREN"""
    test_l, test_el = p[2]
    if test_el is not None:
        p[0] = test_el
    else:
        p[0] = ast.Tuple(to_rlist(test_l), ast.Load())

# trailer: '(' [arglist] ')' | '[' subscriptlist ']' | '.' NAME
def p_trailer_call(p):
    """trailer : LPAREN arglist RPAREN"""
    pair_it = send_next_iter(reversed(p[2]))

    args = []   # positional arguments
    for kw, arg in pair_it:
        if kw:
            pair_it.send((kw, arg))
            break
        args.append(arg)

    keywords = []   # keyword arguments
    seen = set()
    for kw_wloc, arg in pair_it:
        if not kw_wloc:
            raise MySyntaxError('non-keyword arg after keyword arg',
                                node_loc(arg, p))
        kw, loc = kw_wloc
        if kw in seen:
            raise MySyntaxError('keyword argument repeated', loc)
        else:
            seen.add(kw)
        keywords.append(set_loc(ast.keyword(kw, arg), loc))

    p[0] = (lambda expr: ast.Call(expr, args, keywords, None, None),
            ploc(p, 1))

def p_argument_0(p):
    """argument : ID EQUALS test"""
    p[0] = (pwloc(p, 1), p[3])

def p_argument_1(p):
    """argument : test"""
    p[0] = (None, p[1])


def p_trailer_attr(p):
    """trailer    : PERIOD ID
       my_trailer : empty  ID"""
    attr = p[2]
    p[0] = (lambda expr: ast.Attribute(expr, attr, ast.Load()),
            ploc(p, 1))


def p_trailer_item(p):
    """trailer    : LBRACKET test RBRACKET"""
    item = ast.Index(p[2])
    p[0] = (lambda expr: ast.Subscript(expr, item, ast.Load()),
            ploc(p, 1))


def p_my_trailer(p):
    """my_trailer : trailer"""
    p[0] = p[1]


def p_trailer_my_setter_block(p):
    """trailer : mb_period LBRACE docstring my_setters RBRACE"""
    setters = p[4]
    docstring = p[3]
    if docstring is not None:
        setters.append(docstring)

    func_args = ast.arguments(args=[ast_self(ast.Param())],
                              vararg=None, kwarg=None, defaults=[])
    setters_func = ast.Lambda(args=func_args,
                              body=ast.List(to_rlist(setters), ast.Load()))

    p[0] = (lambda expr: ast.Call(ast.Name('__my_setter__', ast.Load()),
                                  [expr, setters_func], [], None, None),
            ploc(p, 2))


def p_mb_period(p):
    """mb_period :
       mb_period : PERIOD"""
    p[0] = (len(p) > 1)

def p_docstring_empty(p):
    """docstring :"""
def p_docstring(p):
    """docstring : STRING
       docstring : STRING COMMA"""
    p[0] = set_loc(ast.Tuple([ast_self(),
                             ast.Str('__doc__'),
                             ast.Num(True),
                             ast.Str(p[1])], ast.Load()),
                   ploc(p, 1))


def p_my_setter(p):
    """my_setter : my_trailers COLON test"""

    expr = fold_trailers(ast_self(), p[1])
    if isinstance(expr, ast.Call):
        raise MySyntaxError("can't assign to function call", node_loc(expr, p))

    obj = expr.value  # unfold the outermost trailer

    if isinstance(expr, ast.Attribute):
        target, is_attr = ast.Str(expr.attr), ast.Num(True)
    else:  # ast.Subscript
        target, is_attr = expr.slice.value, ast.Num(False)

    p[0] = copy_loc(ast.Tuple([obj, target, is_attr, p[3]], ast.Load()),
                    expr)


# generic (possibly comma-separated, and with trailing comma) list parsing

def p_list(p):
    """
    stmts :
    trailers :
    my_setters :
    arglist :
    dictentlist :
    """
    p[0] = []

def p_list_head(p):
    """
    arglist : argument
    my_setters : my_setter
    dictentlist : dictent
    """
    p[0] = [p[1]]

def p_list_tail(p):
    """
    stmts : stmt stmts
    trailers : trailer trailers
    my_trailers : my_trailer trailers
    my_setters : my_setter COMMA my_setters
    arglist : argument COMMA arglist
    dictentlist : dictent COMMA dictentlist
    """
    l = p[0] = p[len(p)-1]
    l.append(p[1])


def p_empty(p):
    """empty : """
    pass


def p_error(t):
    if t is not None:
        raise MySyntaxError("Unexpected '{0}' token".format(t.value),
                            lex.loc(t))
    else:
        raise MySyntaxError("Premature end of file")


make_yacc = functools.partial(ply.yacc.yacc,
                              write_tables=False,
                              debug=False,
                              errorlog=ply.yacc.NullLogger())

parsermap = {
    'exec': make_yacc(start='exec_start'),
    'eval': make_yacc(start='eval_start'),
}

# The main entry point.

def parse(source, filename='<unknown>', mode='exec', **kwargs):
    """
    Parses the given source and returns the result.

    Args:
        source (str): data to parse
        filename (str): file name to report in case of errors
        mode (str): type of input to expect:
            it can be 'exec' if source consists of a sequence of statements,
            or 'eval' if it consists of a single expression

        **kwargs are passed directly to the underlying PLY parser

    Returns:
        ast.Module object

    Note:
        This function is NOT reentrant.
    """
    try:
        p = parsermap[mode]
    except KeyError:
        raise ValueError("parse() mode arg must be 'exec' or 'eval'")

    l = lex.lexer.clone()
    l.fileinfo = Fileinfo(source, filename)
    try:
        ast_root = p.parse(source, lexer=l, tracking=True, **kwargs)
        return ast.fix_missing_locations(ast_root)

    except MySyntaxError as e:
        raise SyntaxError(*e.args)


if __name__ == "__main__":
    source = """
    x::module {
        .{}.foo: [cc],
        files: ["foo.c"],
    };
    foo {"doc", bar: baz};
    """
    from mako._ast_util import SourceGenerator as SG

    def p(node):
        sg=SG('    ')
        sg.visit(node)
        return ''.join(sg.result)

    print p(parse(source))

