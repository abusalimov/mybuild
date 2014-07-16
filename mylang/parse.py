"""
PLY-based parser for Myfile grammar.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from _compat import *

import ast
import functools
import inspect
import ply.yacc

from mylang import lex
from mylang.location import Fileinfo
from mylang.location import Location

from util.operator import getter


# Location tracking.

def node_loc(ast_node, p):
    return Location.from_ast_node(ast_node, p.lexer.fileinfo)

def ploc(p, i=1):
    return Location(p.lexer.fileinfo, p.lineno(i), p.lexpos(i))

def set_loc(ast_node, loc):
    return loc.init_ast_node(ast_node)

def set_loc_p(ast_node, p, i=1):
    return set_loc(ast_node, ploc(p, i))

copy_loc = ast.copy_location


# Some utils.

class MySyntaxError(Exception):
    """Stub class for using instead of standard SyntaxError because the latter
    has the special meaning for PLY."""

    def __init__(self, msg, loc=None):
        loc_args = (loc.to_syntax_error_tuple(),) if loc is not None else ()
        super(MySyntaxError, self).__init__(msg, *loc_args)


# ast wrappers (py3k compat + arg defaults).

try:
    ast_const = ast.NameConstant

except AttributeError:
    def ast_const(const):
        return ast.Name(repr(const), ast.Load())

_const_names = {
    'None':  None,
    'False': False,
    'True':  True,
}

def ast_name(name, ctx=None):
    if name in _const_names:
        return ast_const(_const_names[name])
    if ctx is None:
        ctx = ast.Load()
    return ast.Name(name, ctx)

def ast_call(func, args=None, keywords=None, starargs=None, kwargs=None):
    return ast.Call(func, args or [], keywords or [], starargs, kwargs)

if py3k:
    def ast_arg(name):
        return ast.arg(name, None)
    ast_arg_name = getter.arg

    try:
        def ast_arguments(args=None, vararg=None, kwarg=None, defaults=None):
            return ast.arguments(args or [], vararg, [], [], kwarg,
                                 defaults or [])
        ast_arguments()

    except TypeError:
        # earlier versions of py3k have slightly different ast
        def ast_arguments(args=None, vararg=None, kwarg=None, defaults=None):
            if vararg is not None:
                varargarg = vararg.arg
                varargannotation = vararg.annotation
            else:
                varargarg = varargannotation = None
            if kwarg is not None:
                kwargarg = kwarg.arg
                kwargannotation = kwarg.annotation
            else:
                kwargarg = kwargannotation = None
            return ast.arguments(args or [], varargarg, varargannotation,
                                 [], kwargarg, kwargannotation,
                                 defaults or [], [])

    def ast_funcdef(name, args, body):
        return ast.FunctionDef(name, args, body, [], None)

else:
    def ast_arg(name):
        return ast.Name(name, ast.Param())
    ast_arg_name = getter.id

    def ast_arguments(args=None, vararg=None, kwarg=None, defaults=None):
        return ast.arguments(args or [], vararg, kwarg, defaults or [])

    def ast_funcdef(name, args, body):
        return ast.FunctionDef(name, args, body, [])


# p_func definition helpers.

def _rule_indices_from_argspec(func, with_p=True):
    args, _, _, defaults = inspect.getargspec(inspect.unwrap(func))
    nr_args = len(args)
    defaults = list(defaults) if defaults is not None else []

    if with_p:
        if not nr_args:
            raise TypeError("need at least 'p' argument")
        if len(defaults) == nr_args:
            defaults = defaults[1:]
        nr_args -= 1

    if None in defaults:
        def_nones = defaults[defaults.index(None):]
        if def_nones.count(None) != len(def_nones):
            raise TypeError("index argument after 'None'")

        def_indices = defaults[:-len(def_nones)]
    else:
        def_indices = defaults

    return list(range(1, nr_args-len(defaults)+1)) + def_indices

def _symbol_at(p, idx):
    return p[idx + (idx < 0 and len(p))]
def _symbols_at(p, indices):
    return [_symbol_at(p, idx) for idx in indices]

def rule(func):
    indices = _rule_indices_from_argspec(func)
    @functools.wraps(func)
    def decorated(p):
        p[0] = func(p, *_symbols_at(p, indices))
    return decorated

def wloc_of(idx):
    def decorator(func):
        @functools.wraps(func)
        def decorated(p, *symbols):
            return func(p, *symbols), ploc(p, idx)
        return decorated
    return decorator

wloc = wloc_of(1)

def rule_wloc(func):
    return rule(wloc(func))


# Runtime intrinsics and internal auxiliary names.

MY_NEW_TYPE    = '__my_new_type__'
MY_CALL_ARGS   = '__my_call_args__'

AUX_DELEGATE   = '<delegate>'
AUX_SUITE_FMT  = '<suite_{0}>'


# AST fragments builders.

def build_node(builder_wloc, expr=None):
    builder, loc = builder_wloc
    return set_loc(builder(expr) if expr is not None else builder(), loc)

def build_chain(builder_wlocs, expr=None):
    for builder_wloc in builder_wlocs:
        expr = build_node(builder_wloc, expr)
    return expr

def build_typedef(body_name, metatype, namefrags=None, call_builder=None):
    # metatype { } ->
    # __my_new_type__(__suite, metatype)
    #
    # metatype namefrags { } ->
    # __my_new_type__(__suite, metatype, 'namefrags')
    #
    # metatype namefrags(...) { } ->
    # __my_new_type__(__suite, metatype, 'namefrags', *__my_call_args__(...))
    args = [body_name, metatype]
    starargs = None

    if namefrags is not None:
        qualname = '.'.join(namefrag().id for namefrag, loc in namefrags)
        args.append(ast.Str(qualname))

    if call_builder is not None:
        starargs = build_node(call_builder, ast_name(MY_CALL_ARGS))
        if not (starargs.args or
                starargs.keywords or
                starargs.starargs or
                starargs.kwargs):
            starargs = None  # optimize out

    ret_call = ast_call(ast_name(MY_NEW_TYPE), args,
                        starargs=starargs)
    return copy_loc(ret_call, metatype)


# Here go grammar definitions for PLY.

tokens = lex.tokens


def p_begin_bblock(p):
    """begin_local_bblock : LBRACE
       begin_global_bblock :"""
    bblock_stack = p.parser.bblock_stack

    bblock = []
    if not bblock_stack:  # outermost => global scope
        bblock.append(ast.Global([]))

    bblock_stack.append(bblock)

def p_end_bblock(p):
    """end_local_bblock : RBRACE
       end_global_bblock :"""
    p.parser.bblock_stack.pop()


def docstring(stmts):
    if (stmts and
        isinstance(stmts[0], ast.Expr) and
        isinstance(stmts[0].value, ast.Str)):
        return stmts[0]


@rule
def p_exec_start(p, suite_func=2):
    """exec_start : begin_global_bblock suite end_global_bblock"""
    # stms... ->
    #
    # @__my_new_type__
    # def __suite():
    #     global foo, bar, baz
    #     ...
    # del __suite

    suite_func.name = AUX_SUITE_FMT.format('global')
    suite_func.decorator_list = [ast_name(MY_NEW_TYPE)]
    del_stmt = ast.Delete([ast_name(suite_func.name, ast.Del())])

    module_body = [suite_func, del_stmt]

    doc_node = docstring(suite_func.body)
    if doc_node is not None:
        module_body.insert(0, doc_node)

    return ast.Module(module_body)

@rule
def p_typedef_body(p, suite_func=2):
    """typedef_body : begin_local_bblock suite end_local_bblock"""
    bblock_stack = p.parser.bblock_stack
    bblock = bblock_stack[-1]

    suite_func.name = AUX_SUITE_FMT.format('{0}_{1}'.format(len(bblock_stack),
                                                            len(bblock)))
    bblock.append(suite_func)

    return set_loc_p(ast_name(suite_func.name), p)


@rule
def p_suite(p, mb_docstring=2, stmts=-1):
    """suite : skipnl mb_docstring stmts"""
    bblock_stack = p.parser.bblock_stack
    bblock = bblock_stack[-1]

    has_docstring = (mb_docstring is not None)
    if has_docstring:
        doc_node = ast.Expr(build_node(mb_docstring))
        stmts.insert(0, doc_node)

    # always leave a docstring (if any) first
    ins_idx = int(has_docstring)
    stmts[ins_idx:ins_idx] = bblock

    if not stmts:
        stmts.append(ast.Pass())  # otherwise all hell will break loose

    is_global = (len(bblock_stack) == 1)
    if not is_global:
        suite_args = ast_arguments([ast_arg(AUX_DELEGATE)])
    else:
        suite_args = ast_arguments()
    suite_func = ast_funcdef(None, suite_args, stmts)

    return suite_func


@rule
def p_stmt_binding(p, namefrags_colons_value):
    """stmt : binding"""
    bblock_stack = p.parser.bblock_stack
    namefrags, colons, value = namefrags_colons_value

    is_class_binding = (colons == '::')

    is_global = (len(bblock_stack) == 1)
    if not is_global:
        value = ast.Lambda(ast_arguments([ast_arg('self')]), value)
        target = build_chain(namefrags, ast_name(AUX_DELEGATE))
    else:
        target = build_chain(namefrags)

        if isinstance(target, ast.Name):
            bblock = bblock_stack[0]
            global_stmt = bblock[0]
            assert isinstance(global_stmt, ast.Global)

            if target.id not in global_stmt.names:
                global_stmt.names.append(target.id)

    target.ctx = ast.Store()
    return copy_loc(ast.Assign([target], value), target)


@rule  # metatype target(): { ... }
def p_binding_typedef(p, metatype_builders=2, namefrags=3, mb_call_builder=4,
                      colons=5, body_name=-1):
    """binding : nl_off namefrags namefrags mb_call colons nl_on typedef_body"""
    # Here namefrags is used instead of pytest to work around
    # a reduce/reduce conflict with simple binding (pytest/namefrags).
    return (namefrags, colons,
            build_typedef(body_name, build_chain(metatype_builders),
                          namefrags, mb_call_builder))

@rule  # target1: ...
def p_binding_simple(p, namefrags=2, colons=3, value=-1):
    """binding : nl_off namefrags colons nl_on test"""
    return namefrags, colons, value

@rule  # : -> False,  :: -> True
def p_colons(p, colons):
    """colons : COLON
       colons : DOUBLECOLON"""
    return colons


@rule
def p_test(p, test):
    """test : pytest
       test : mytest"""
    return test

@rule
def p_pytest(p, builders):
    """pytest : name_trailers
       pytest : pyatom_trailers
       pytest : myatom_trailers_plus"""
    return build_chain(builders)

@rule
def p_mytest(p, builder):
    """mytest : myatom"""
    return build_node(builder)


@rule_wloc
def p_myatom_closure(p, closure):
    """myatom : LBRACE RBRACE"""
    return lambda: ast_name('XXX')
    raise NotImplementedError

@rule_wloc
def p_myatom_typedef(p, metatype, body_name):
    """myatom : pytest typedef_body"""
    return lambda: build_typedef(body_name, metatype)

@rule_wloc
def p_myatom_typedef_named(p, metatype, namefrags, mb_call_builder, body_name):
    """myatom : pytest namefrags mb_call typedef_body"""
    return lambda: build_typedef(body_name, metatype, namefrags, mb_call_builder)


@rule_wloc
def p_pyatom_num(p, n):
    """pyatom : NUMBER"""
    return lambda: ast.Num(n)

@rule_wloc
def p_pyatom_str_mb_docstring(p, s):
    """pyatom       : STRING
       mb_docstring : STRING stmtdelim"""
    return lambda: ast.Str(s)

def p_mb_docstring_empty(p):
    """mb_docstring : empty"""

@rule_wloc
def p_pyatom_parens_or_tuple(p, testlist=2):  # (item, ...)
    """pyatom : LPAREN testlist RPAREN"""
    test_l, test_el = testlist
    if test_el is not None:
        return lambda: test_el
    else:
        return lambda: ast.Tuple(test_l, ast.Load())

@rule_wloc
def p_pyatom_list(p, testlist=2):  # [item, ...]
    """pyatom : LBRACKET testlist RBRACKET"""
    test_l = testlist[0]
    return lambda: ast.List(test_l, ast.Load())

@rule_wloc
def p_pyatom_dict(p, kv_pairs=2):  # [key: value, ...], [:]
    """pyatom : LBRACKET dictents RBRACKET
       pyatom : LBRACKET COLON RBRACKET"""
    if kv_pairs != ':':
        keys, values = map(list, zip(*kv_pairs))
    else:
        keys, values = [], []

    return lambda: ast.Dict(keys, values)

@rule
def p_dictent(p, key, value=3):
    """dictent : test COLON test"""
    return key, value


@rule
def p_trailer_call(p, call):
    """trailer : call
       mb_call : call
       mb_call : empty"""
    return call

@rule_wloc
def p_call(p, kw_arg_pairs=2):  # x(arg, kw=arg, ...)
    """call : LPAREN arguments RPAREN"""
    args      = []  # positional arguments
    keywords  = []  # keyword arguments
    seen_kw   = set()

    for kw_wloc, arg in kw_arg_pairs:
        if kw_wloc is None:
            if seen_kw:
                raise MySyntaxError('non-keyword arg after keyword arg',
                                    node_loc(arg, p))
            args.append(arg)

        else:
            kw, loc = kw_wloc
            if kw in seen_kw:
                raise MySyntaxError('keyword argument repeated', loc)
            else:
                seen_kw.add(kw)
            keywords.append(set_loc(ast.keyword(kw, arg), loc))

    return lambda expr: ast_call(expr, args, keywords)

@rule
def p_argument_pos(p, value):
    """argument : test"""
    return None, value

@rule
def p_argument_kw(p, key, value=3):
    """argument : ID EQUALS test"""
    kw_wloc = key, ploc(p)
    return kw_wloc, value

@rule_wloc
def p_trailer_attr_or_name(p, name=-1):  # x.attr or name
    """trailer : PERIOD ID
       name    : ID"""
    def builder(expr=None):
        if expr is not None:
            return ast.Attribute(expr, name, ast.Load())
        else:
            return ast_name(name)
    return builder

@rule_wloc
def p_trailer_item(p, item=2):  # x[item]
    """trailer : LBRACKET test RBRACKET"""
    return lambda expr: ast.Subscript(expr, ast.Index(item), ast.Load())


# NIY

def p_trailer_multigetter(p):  # x.[attr, [item], (call), ...]
    """trailer : PERIOD LBRACKET getters RBRACKET"""
    raise NotImplementedError

def p_getter(p):
    """getter : name_trailers"""
    raise NotImplementedError

def p_trailer_multisetter(p):  # x.[attr: value, [item]: value, ...]
    """trailer : PERIOD LBRACKET setters RBRACKET"""
    raise NotImplementedError

def p_setter(p):
    """setter : name_trailers COLON test"""
    raise NotImplementedError


# testlist is a pair of [list of elements] and a single element (if any)

def p_testlist(p):
    """testlist : testlist_plus mb_comma"""
    p[0] = p[1]

def p_testlist_empty(p):
    """testlist :"""
    p[0] = [], None

def p_testlist_single(p):
    """testlist_plus : test"""
    el = p[1]
    p[0] = [el], el

def p_testlist_list(p):
    """testlist_plus : testlist_plus COMMA test"""
    l, _ = p[1]
    l.append(p[3])
    p[0] = l, None


# generic (possibly comma-separated, and with trailing comma) list parsing

@rule
def p_list_head(p, el):
    """
    namefrags          :  name

    stmts_plus         :  stmt
    arguments_plus     :  argument
    dictents_plus      :  dictent
    getters_plus       :  getter
    setters_plus       :  setter
    """
    return [el]

@rule
def p_list_tail(p, l, el=-1):
    """
    namefrags          :  namefrags       PERIOD     name

    stmts_plus         :  stmts_plus      stmtdelim  stmt
    arguments_plus     :  arguments_plus  COMMA      argument
    dictents_plus      :  dictents_plus   COMMA      dictent
    getters_plus       :  getters_plus    COMMA      getter
    setters_plus       :  setters_plus    COMMA      setter

    trailers_plus      :  trailers                   trailer
    """
    l.append(el)
    return l

@rule
def p_rlist_tail(p, el, l=-1):
    """
    name_trailers        :  name                 trailers
    pyatom_trailers      :  pyatom               trailers
    myatom_trailers_plus :  myatom               trailers_plus
    """
    l.insert(0, el)
    return l

@rule
def p_list_alias(p, l):
    """
    trailers             :  empty_list
    trailers             :  trailers_plus

    stmts              :  stmts_plus      mb_stmtdelim
    arguments          :  arguments_plus  mb_comma
    dictents           :  dictents_plus   mb_comma
    getters            :  getters_plus    mb_comma
    setters            :  setters_plus    mb_comma

    stmts              :  empty_list
    arguments          :  empty_list
    getters            :  empty_list
    """
    return l

@rule
def p_empty_list(p):
    """empty_list :"""
    return []

def p_mb_comma(p):
    """mb_comma :
       mb_comma : COMMA"""


# new line control and stuff

def p_nl_off(p):
    """nl_off :"""
    p.lexer.ignore_newline_stack[-1] += 1

def p_nl_on(p):
    """nl_on :"""
    # Work around a 'nl_on' preceding a token pushing to the
    # ignore_newline_stack (aka 'ins' below).
    # In this case the 'nl_on' gets reduced _after_ handling the token,
    # and naive decreasing of the stack top would underflow it.
    was_ins_pushing_token = (p.lexer.ignore_newline_stack[-1] == 0)
    p.lexer.ignore_newline_stack[-1 - was_ins_pushing_token] -= 1

def p_skipnl(p):
    """skipnl :
       skipnl : skipnl NEWLINE"""

def p_stmtdelim(p):
    """stmtdelim : mb_stmtdelim NEWLINE
       stmtdelim : mb_stmtdelim SEMI"""

def p_mb_stmtdelim(p):
    """mb_stmtdelim :
       mb_stmtdelim : stmtdelim"""

def p_empty(p):
    """empty :"""

def p_error(t):
    if t is not None:
        raise MySyntaxError("Unexpected {0!r} token".format(t.value),
                            lex.loc(t))
    else:
        raise MySyntaxError("Premature end of file")


# That's it!

parser = ply.yacc.yacc(start='exec_start',
                       errorlog=ply.yacc.NullLogger(), debug=False,
                       write_tables=False)

# The main entry point.

def parse(source, filename='<unknown>', mode='exec', **kwargs):
    """
    Parses the given source and returns the result.

    Args:
        source (str): data to parse
        filename (str): file name to report in case of errors
        mode (str): type of input to expect:
            it can be 'exec' only (constrained by design).

        **kwargs are passed directly to the underlying PLY parser

    Returns:
        ast.Module object

    Note:
        This function is NOT reentrant.
    """
    if mode != 'exec':
        raise NotImplementedError("Only 'exec' mode is supported")

    p = parser

    p.bblock_stack = []

    l = lex.lexer.clone()
    l.fileinfo = Fileinfo(source, filename)
    try:
        ast_root = p.parse(source, lexer=l, tracking=True, **kwargs)
        return ast.fix_missing_locations(ast_root)

    except MySyntaxError as e:
        raise SyntaxError(*e.args)


if __name__ == "__main__":
    source = """
    "module docstring"

    foo // comment
    bar /*
    */ baz

    {}
    {;}
    {:;}
    {:slf;}
    {:||}
    {|arg|;}
    {:|arg={foo:bar}|}
    {:slf|arg|}

    {
    |
    xxx
    |
    }

    {:s
    |
    yyy
    |
    }

    module() foo: bar= {
        x[foo]: [cc]
        files: ["foo.c"]
    }
    """
    from mako._ast_util import SourceGenerator

    class SG(SourceGenerator):
        def visit_Delete(self, node):
            super(SG, self).visit_Delete(node.targets)  # workaround

    def pr(node):
        sg=SG('    ')
        sg.visit(node)
        return ''.join(sg.result)

    ast_root = parse(source, debug=0)

    compile(ast_root, "", 'exec')
    print(pr(ast_root))
    # print(ast.dump(ast_root))

