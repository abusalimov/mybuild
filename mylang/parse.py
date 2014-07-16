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

    def ast_funcdef(name, args, body, decos=None):
        return ast.FunctionDef(name, args, body or [ast.Pass()], decos or [],
                               None)

else:
    def ast_arg(name):
        return ast.Name(name, ast.Param())
    ast_arg_name = getter.id

    def ast_arguments(args=None, vararg=None, kwarg=None, defaults=None):
        return ast.arguments(args or [], vararg, kwarg, defaults or [])

    def ast_funcdef(name, args, body, decos=None):
        return ast.FunctionDef(name, args, body or [ast.Pass()], decos or [])

try:
    ast.Try

except AttributeError:
    def ast_try_except(body, handlers, orelse=None):
        return ast.TryExcept(body, handlers, orelse or [ast.Pass()])
else:
    def ast_try_except(body, handlers, orelse=None):
        return ast.Try(body, handlers, orelse or [ast.Pass()], [ast.Pass()])


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
MY_EXEC_MODULE = '__my_exec_module__'

CLS_ARG        = 'cls'
SELF_ARG       = 'self'

_RESULT_TMP    = '<tmp>'
_AUX_NAME_FMT  = '<aux-{0}-{1}>'
_MODULE_EXEC   = '<trampoline>'
_EXEC_ARG      = '<exec>'


# AST fragments builders.

def build_node(builder_wloc, expr=None):
    builder, loc = builder_wloc
    return set_loc(builder(expr) if expr is not None else builder(), loc)

def build_chain(builder_wlocs, expr=None):
    for builder_wloc in builder_wlocs:
        expr = build_node(builder_wloc, expr)
    return expr

def build_typedef(body, metatype, namefrags=None, call_builder=None):
    # metatype { ... } ->
    # __my_new_type__([...], metatype)
    #
    # metatype namefrags { ... } ->
    # __my_new_type__([...], metatype, 'namefrags')
    #
    # metatype namefrags(...) { ... } ->
    # __my_new_type__([...], metatype, 'namefrags', *__my_call_args__(...))
    doc_str, bindings_list, typeret_func = body

    args = [doc_str, bindings_list, typeret_func, metatype]
    starargs = None

    if namefrags is not None:
        qualname = '.'.join(namefrag().id for namefrag, loc in namefrags)
        args.append(ast.Str(qualname))

    if call_builder is not None:
        starargs = build_node(call_builder, ast_name(MY_CALL_ARGS))
        # but:
        if not (starargs.args or
                starargs.keywords or
                starargs.starargs or
                starargs.kwargs):
            starargs = None  # optimize out

    ret_call = ast_call(ast_name(MY_NEW_TYPE), args, starargs=starargs)
    return copy_loc(ret_call, metatype)


# Dealing with statements.

class BuildingBlock(object):
    """Building Block encapsulates a sequence of statements."""

    def __init__(self, parent=None):
        super(BuildingBlock, self).__init__()
        self.parent = parent

        self.stmts = []
        self.aux_cnt = 0
        if parent is not None:
            self.depth = parent.depth + 1
        else:
            self.depth = 0

    @property
    def is_global(self):
        return self.parent is None

    @property
    def docstring_stmt(self):
        if (self.stmts and
            isinstance(self.stmts[0], ast.Expr) and
            isinstance(self.stmts[0].value, ast.Str)):
            return self.stmts[0]

    def append(self, stmt):
        self.stmts.append(stmt)

    def make_returning(self):
        ReturningTransformer().modify_stmts_list(self.stmts)

    def make_assigning(self, name=_RESULT_TMP):
        AssigningTransformer(name).modify_stmts_list(self.stmts)
        return ast_name(name)

    def new_aux_name(self):
        cnt = self.aux_cnt
        self.aux_cnt = cnt + 1
        return _AUX_NAME_FMT.format(self.depth, cnt)

    def build_func_from(self, stmts, arguments, name=None):
        if name is None:
            name = self.new_aux_name()
        self.append(ast_funcdef(name, arguments, stmts))
        return ast_name(name)

    def fold_into_func(self, arguments, name=None):
        self.make_returning()
        return self.parent.build_func_from(self.stmts, arguments, name)

    def fold_into_binding(self, static=False):
        module_level = self.parent.is_global

        if module_level and static:
            raise MySyntaxError("Unexpected static binding at module level")

        if not module_level:
            args = [ast_arg(CLS_ARG if static else SELF_ARG)]
        else:
            args = []

        return self.fold_into_func(ast_arguments(args))


class ResultingTransformer(ast.NodeTransformer):

    def modify_stmts_list(self, stmts):
        if stmts:
            value = self.visit(stmts.pop())
        else:
            value = self.create_noresult()

        if isinstance(value, ast.AST):
            stmts.append(value)
        elif value is not None:
            stmts.extend(value)

        return stmts

    def visit_FunctionDef(self, node):
        raise ValueError('Unexpected FunctionDef as the last stmt of bblock')

    def visit_Expr(self, node):
        return copy_loc(self.transform_expr(node.value), node)

    def visit_If(self, node):
        for bblock in node.body, node.orelse:
            self.modify_stmts_list(bblock)
        return node

    def visit_Return(self, node):
        return node

    def noresult_visit(self, node):
        return [node] + self.modify_stmts_list([])

    visit_Delete    = noresult_visit
    visit_Assign    = noresult_visit
    visit_AugAssign = noresult_visit
    visit_Pass      = noresult_visit

    def create_noresult(self):
        return self.transform_expr(ast_const(None))

    def transform_expr(self, expr):
        raise NotImplementedError


class ReturningTransformer(ResultingTransformer):

    def create_noresult(self):
        # This is the last stmt anyway, 'return None' is implied.
        return None

    def transform_expr(self, expr):
        return ast.Return(expr)

class AssigningTransformer(ResultingTransformer):

    def __init__(self, name):
        super(AssigningTransformer, self).__init__()
        self.name = name

    def transform_expr(self, expr):
        return ast.Assign([ast_name(self.name, ast.Store())], expr)


def emit_stmt(p, stmt):
    p.parser.bblock.append(stmt)

def push_new_bblock(p):
    p.parser.bblock = BuildingBlock(p.parser.bblock)

def pop_bblock(p):
    bblock = p.parser.bblock
    p.parser.bblock = bblock.parent
    return bblock


# Here go grammar definitions for PLY.

tokens = lex.tokens

def p_new_bblock(p):
    """new_bblock :"""
    push_new_bblock(p)

@rule
def p_exec_start(p, docstring_bindings=-1):
    """exec_start : new_bblock typesuite"""
    # stmts... ->
    #
    # try:
    #     @__my_exec_module__
    #     def __suite(__delegate):
    #         ...
    #         global foo, bar, baz
    #         foo, bar, baz = __delegate([...])
    #
    # except __my_exec_module__:
    #     pass
    #
    # N.B. This voodoo is to avoid storing __suite name into global module
    # dict. __my_exec_module__ applied as a decorator executes a function
    # being decorated (__suite in this case) and throws 'itself' instead
    # of returning as normal).
    # Likewise any auxiliary function is defined local to the __suite.
    #
    bblock = pop_bblock(p)

    doc_str, bindings_list = docstring_bindings

    exec_call = ast_call(ast_name(MY_EXEC_MODULE), args=[bindings_list])

    binding_idfs = [binding_tuple.elts[0].s
                    for binding_tuple in bindings_list.elts]
    binding_names = [ast_name(name, ast.Store()) for name in binding_idfs]

    bblock.append(ast.Global(binding_idfs))
    bblock.append(ast.Assign(binding_names, exec_call))

    suite_func = ast_funcdef(_MODULE_EXEC, ast_arguments([ast_arg(_EXEC_ARG)]),
                             bblock.stmts, decos=[ast_name(MY_EXEC_MODULE)])

    eh_stmt = ast.ExceptHandler(ast_name(MY_EXEC_MODULE), None, [ast.Pass()])
    try_stmt = ast_try_except([suite_func], [eh_stmt])

    module_body = [try_stmt]

    if isinstance(doc_str, ast.Str):
        module_body.insert(0, ast.Expr(doc_str))

    return ast.Module(module_body)

@rule
def p_typebody(p, docstring_bindings=2, typeret_func=-1):
    """typebody : LBRACE typesuite RBRACE typeret"""
    doc_str, bindings_list = docstring_bindings
    return doc_str, bindings_list, typeret_func

@rule
def p_typeret(p):
    """typeret : """
    return ast_const(None)  # stub for further devel

@rule
def p_stmtexpr(p, value):
    """stmtexpr : test"""
    emit_stmt(p, ast.Expr(value))

@rule
def p_typesuite(p, bindings=-1):
    """typesuite : skipnl typestmts"""
    if bindings and not isinstance(bindings[0], ast.Tuple):
        doc_str = build_node(bindings.pop(0))
    else:
        doc_str = ast_const(None)

    return doc_str, ast.List(bindings, ast.Load())


@rule
def p_typestmt(p, namefrags_colons=-1):
    """typestmt : new_bblock binding_typedef
       typestmt : new_bblock binding_simple"""
    bblock = pop_bblock(p)

    namefrags, colons = namefrags_colons
    qualname = '.'.join(namefrag().id for namefrag, loc in namefrags)
    is_static = (colons == '::')

    func = bblock.fold_into_binding(is_static)

    return ast.Tuple([ast.Str(qualname), ast_const(is_static), func],
                     ast.Load())

@rule  # metatype target(): { ... }
def p_binding_typedef(p, metatype_builders=2, namefrags=3, mb_call_builder=4,
                      colons=5, body=-1):
    # Here namefrags is used instead of pytest to work around
    # a reduce/reduce conflict with simple binding (pytest/namefrags).
    """binding_typedef : nl_off namefrags namefrags mb_call colons nl_on typebody"""
    value = build_typedef(body, build_chain(metatype_builders),
                          namefrags, mb_call_builder)
    emit_stmt(p, ast.Expr(value))
    return namefrags, colons

@rule  # target1: ...
def p_binding_simple(p, namefrags=2, colons=3):
    """binding_simple : nl_off namefrags colons nl_on stmtexpr"""
    return namefrags, colons

@rule  # : -> False,  :: -> True
def p_colons(p, colons):
    """colons : COLON
       colons : DOUBLECOLON"""
    return colons


@rule
def p_test(p, test):
    """test : pytest
       test : mystub"""
    return test

@rule
def p_pytest(p, stub, builders):
    """pytest : pystub trailers
       pytest : mystub trailers_plus"""
    return build_chain(builders, stub)

@rule
def p_stub(p, builder):
    """pystub : name
       pystub : pyatom
       mystub : myatom"""
    return build_node(builder)


@rule_wloc
def p_myatom_closure(p, closure):
    """myatom : LBRACE RBRACE"""
    return lambda: ast_name('XXX')
    raise NotImplementedError

@rule_wloc
def p_myatom_typedef(p, metatype, body):
    """myatom : pytest typebody"""
    return lambda: build_typedef(body, metatype)

@rule_wloc
def p_myatom_typedef_named(p, metatype, namefrags, mb_call_builder, body):
    """myatom : pytest namefrags mb_call typebody"""
    return lambda: build_typedef(body, metatype, namefrags, mb_call_builder)


@rule_wloc
def p_pyatom_num(p, n):
    """pyatom : NUMBER"""
    return lambda: ast.Num(n)

@rule
def p_pyatom_string(p, string):
    """pyatom : string"""
    return string

@rule_wloc
def p_string(p, s):
    """string : STRING"""
    return lambda: ast.Str(s)

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
    """getter : name trailers"""
    raise NotImplementedError

def p_trailer_multisetter(p):  # x.[attr: value, [item]: value, ...]
    """trailer : PERIOD LBRACKET setters RBRACKET"""
    raise NotImplementedError

def p_setter(p):
    """setter : name trailers COLON test"""
    raise NotImplementedError


# testlist is a pair of [list of elements] and a single element (if any)

@rule
def p_testlist(p, l):
    """testlist : testlist_plus mb_comma"""
    return l

@rule
def p_testlist_empty(p):
    """testlist :"""
    return [], None

@rule
def p_testlist_single(p, el):
    """testlist_plus : test"""
    return [el], el

@rule
def p_testlist_list(p, l_el, el=-1):
    """testlist_plus : testlist_plus COMMA test"""
    l, _ = l_el
    l.append(el)
    return l, None


# generic (possibly comma-separated, and with trailing comma) list parsing

@rule
def p_list_head(p, el):
    """
    namefrags          :  name

    typestmts_plus     :  string
    typestmts_plus     :  typestmt
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

    typestmts_plus     :  typestmts_plus  stmtdelim  typestmt
    arguments_plus     :  arguments_plus  COMMA      argument
    dictents_plus      :  dictents_plus   COMMA      dictent
    getters_plus       :  getters_plus    COMMA      getter
    setters_plus       :  setters_plus    COMMA      setter

    trailers_plus      :  trailers                   trailer
    """
    l.append(el)
    return l

@rule
def p_list_alias(p, l):
    """
    trailers             :  empty_list
    trailers             :  trailers_plus

    typestmts          :  typestmts_plus  mb_stmtdelim
    arguments          :  arguments_plus  mb_comma
    dictents           :  dictents_plus   mb_comma
    getters            :  getters_plus    mb_comma
    setters            :  setters_plus    mb_comma

    typestmts          :  empty_list
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

    pr = parser

    lx = lex.lexer.clone()
    lx.fileinfo = Fileinfo(source, filename)

    pr.bblock = None
    try:
        ast_root = pr.parse(source, lexer=lx, tracking=True, **kwargs)
        return ast.fix_missing_locations(ast_root)

    except MySyntaxError as e:
        raise SyntaxError(*e.args)

    finally:
        del pr.bblock


if __name__ == "__main__":
    source = """
    "module docstring"
    y: mod { "doc"; a::s }
    a: 0; b: 1; c: 2
    x: (call(s,d,f,x=0,y=1,z=2), [1,2,3,4], ["a":1, "b":2, "c":3, "d":4], [:])
    module foo: {
        option bar(metaclass=type _(type){}):: {}
        tools:: [cc]
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

