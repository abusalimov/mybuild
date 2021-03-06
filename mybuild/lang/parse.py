"""
PLY-based parser for Myfile grammar.
"""
from __future__ import absolute_import, division, print_function
from mybuild._compat import *

import functools
import itertools
import ply.yacc
from collections import namedtuple, OrderedDict

from mybuild.lang import lex, x_ast as ast
from mybuild.lang.helpers import rule
from mybuild.lang.location import Fileinfo, Location
from mybuild.util.operator import getter


__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


# Runtime intrinsics and internal auxiliary names.

MY_NEW_TYPE      = '__my_new_type__'
MY_NEW_NAMESPACE = '__my_new_namespace__'
MY_CALL_ARGS     = '__my_call_args__'
MY_EXEC_MODULE   = '__my_exec_module__'

DFL_TYPE_NAME  = '_'
CLS_ARG        = 'cls'
SELF_ARG       = 'self'

_RESULT_TMP    = '<tmp>'
_AUX_NAME_FMT  = '<aux-{0}-{1}>'
_AUX_VAR_NAME_FMT  = '<aux-{0}-{1}>'
_MODULE_EXEC   = '<trampoline>'
_MODULE_NAME   = '<module>'


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


def wloc(func):
    @functools.wraps(func)
    def decorated(p, *symbols):
        return func(p, *symbols), ploc(p)
    return decorated

def rule_wloc(func):
    return rule(wloc(func))


# AST fragments builders.

class Binding(namedtuple('Binding', 'qualname, name_locs, func, is_static')):
    """docstring for Binding"""
    __slots__ = ()

    def __str__(self):
        return '.'.join(self.qualname)

def name_builder(name):
    def builder(expr=None):
        if expr is not None:
            return ast.Attribute(expr, name, ast.Load())
        else:
            return ast.x_Name(name)
    return builder

def build_node(builder_wloc, expr=None):
    builder, loc = builder_wloc
    if not callable(builder):
        builder = name_builder(builder)
    return set_loc(builder(expr) if expr is not None else builder(), loc)

def build_chain(builder_wlocs, expr=None):
    for builder_wloc in builder_wlocs:
        expr = build_node(builder_wloc, expr)
    return expr


def groupby_name(bindings, tier=0):
    """
    Groups bindings by the name fragment specified by tier. Input bindings
    can be not sorted. The order of the bindings remains initial in scope of
    its group.

    Yields:
        (name, [binding(s)...]) tuples.
    """
    res = OrderedDict()
    for binding in bindings:
        name_at_tier = binding.qualname[tier]
        if name_at_tier in res:
            res[name_at_tier].append(binding)
        else:
            res[name_at_tier] = [binding]
    return res

def build_namespace_recursive(bindings, tier):
    keywords  = []

    assert bindings, "A group must not be empty"

    if len(bindings[0].qualname) == tier:
        if len(bindings) > 1:
            loc = bindings[1].name_locs[-1]
            raise MySyntaxError('Namespace element repeated', loc)

        return bindings[0].func

    for name, group in iteritems(groupby_name(bindings, tier)):
        value_ast = build_namespace_recursive(group, tier+1)
        loc = group[0].name_locs[tier]
        keyword = set_loc(ast.keyword(name, value_ast), loc)
        keywords.append(keyword)

    return ast.x_Call(ast.x_Name(MY_NEW_NAMESPACE), keywords=keywords)


def assign_funcs_to_variables(bblock, bindings):
    for binding in bindings:
        var = bblock.new_aux_var_name(binding.qualname[-1])
        value = ast.x_Call(binding.func, [ast.x_Name(SELF_ARG)])

        transformer = AssigningTransformer(var)
        stmt = transformer.transform_expr(value)
        bblock.append(stmt)

        yield Binding(binding.qualname, binding.name_locs,
                      ast.x_Name(var), binding.is_static)


def fold_into_namespace(p, bindings):
    if len(bindings) == 1 and len(bindings[0].qualname) == 1:
        return bindings[0].func
    bblock = BuildingBlock(p.parser.bblock)
    bindings = list(assign_funcs_to_variables(bblock, bindings))
    stmt = ast.Expr(build_namespace_recursive(bindings, 1))
    bblock.append(stmt)
    return bblock.fold_into_binding()


def fold_bindings(p, bindings):
    """
    Folds bindings so that each name matches a correponding namespace.

    Returns:
        An AST structure: [(name, func, is_static)*].
    """
    binding_asts = []

    for name, group in iteritems(groupby_name(bindings)):
        func = fold_into_namespace(p, group)
        loc = group[0].name_locs[0]
        name_str = set_loc(ast.Str(name), loc)

        triple = [name_str, func, ast.x_Const(False)]
        binding_asts.append(ast.Tuple(triple, ast.Load()))

    return ast.List(binding_asts, ast.Load())


def build_typedef(p, body, metatype, qualname=None, call_builder=None):
    # metatype { ... } ->
    # __my_new_type__(metatype, '_', <module>, [...])
    #
    # metatype qualname { ... } ->
    # __my_new_type__(metatype, 'qualname', <module>, [...])
    #
    # metatype qualname(...) { ... } ->
    # __my_new_type__(metatype, 'qualname', <module>, [...],
    #                 *__my_call_args__(...))
    assert len(body) == 2, "body must be a tuple of (doc_str, bindings)"

    if qualname is not None:
        name = '.'.join(name for name, loc in qualname)
    else:
        name = DFL_TYPE_NAME

    doc_str, bindings = body
    binding_list = fold_bindings(p, bindings)

    args = [metatype, ast.Str(name), ast.x_Name(_MODULE_NAME),
            doc_str, binding_list]

    starargs = None
    if call_builder is not None:
        starargs = build_node(call_builder, ast.x_Name(MY_CALL_ARGS))
        # but:
        if not (starargs.args or
                starargs.keywords or
                starargs.starargs or
                starargs.kwargs):
            starargs = None  # optimize out

    ret_call = ast.x_Call(ast.x_Name(MY_NEW_TYPE), args, starargs=starargs)
    return copy_loc(ret_call, metatype)


# Dealing with statements.

class BuildingBlock(object):
    """Building Block encapsulates a sequence of statements."""

    def __init__(self, parent=None):
        super(BuildingBlock, self).__init__()
        self.parent = parent
        self.stmts = []
        self.aux_cnt = 0
        self.aux_var_cnt = 0

        if parent is not None:
            self.depth = parent.depth + 1
        else:
            self.depth = 0

    @property
    def docstring_stmt(self):
        if (self.stmts and
            isinstance(self.stmts[0], ast.Expr) and
            isinstance(self.stmts[0].value, ast.Str)):
            return self.stmts[0]

    def insert(self, index, *stmts):
        self.stmts[index:index] = stmts

    def append(self, *stmts):
        self.stmts.extend(stmts)

    def make_returning(self):
        ReturningTransformer().modify_stmts_list(self.stmts)

    def make_assigning(self, name=_RESULT_TMP):
        AssigningTransformer(name).modify_stmts_list(self.stmts)
        return ast.x_Name(name)

    def new_aux_var_name(self, name):
        cnt = self.aux_var_cnt
        self.aux_var_cnt = cnt + 1
        return _AUX_VAR_NAME_FMT.format(name, cnt)

    def new_aux_name(self):
        cnt = self.aux_cnt
        self.aux_cnt = cnt + 1
        return _AUX_NAME_FMT.format(self.depth, cnt)

    def build_func_from(self, stmts, arguments, name=None):
        if name is None:
            name = self.new_aux_name()
        self.append(ast.x_FunctionDef(name, arguments, stmts))
        return ast.x_Name(name)

    def fold_into_func(self, arguments, name=None):
        self.make_returning()
        return self.parent.build_func_from(self.stmts, arguments, name)

    def fold_into_binding(self, is_static=False):
        args = [ast.x_arg(CLS_ARG if is_static else SELF_ARG)]
        return self.fold_into_func(ast.x_arguments(args))


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
        return self.transform_expr(ast.x_Const(None))

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
        return ast.Assign([ast.Name(self.name, ast.Store())], expr)


def emit_stmt(p, *stmts):
    p.parser.bblock.append(*stmts)

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
    #     def __suite():
    #         global __name__
    #         <module> = __name__
    #         ...
    #         return [...]
    #
    # except __my_exec_module__:
    #     pass
    #
    # N.B. This voodoo is to avoid storing __suite name into global module
    # dict. Applied as a decorator, __my_exec_module__ executes a function
    # being decorated (__suite in this case) and throws 'itself' instead
    # of returning as normal.
    # Likewise any auxiliary function is defined local to the __suite.
    #
    doc_str, bindings = docstring_bindings
    binding_list = fold_bindings(p, bindings)

    bblock = pop_bblock(p)

    bblock.insert(0,
                  ast.Global(['__name__']),
                  ast.Assign([ast.Name(_MODULE_NAME, ast.Store())],
                             ast.x_Name('__name__')))

    bblock.append(ast.Return(binding_list))

    suite_func = ast.x_FunctionDef(_MODULE_EXEC, ast.x_arguments(),
                                   bblock.stmts,
                                   decos=[ast.x_Name(MY_EXEC_MODULE)])

    eh_stmt = ast.ExceptHandler(ast.x_Name(MY_EXEC_MODULE), None, [ast.Pass()])
    try_stmt = ast.x_TryExcept([suite_func], [eh_stmt])

    module_body = [try_stmt]

    if isinstance(doc_str, ast.Str):
        module_body.insert(0, ast.Expr(doc_str))

    return ast.Module(module_body)

@rule
def p_typebody(p, docstring_bindings=2, typeret_func=-1):
    """typebody : LBRACE typesuite RBRACE typeret"""
    return docstring_bindings

@rule
def p_typeret(p):
    """typeret : """
    return None  # stub for further devel

@rule
def p_stmtexpr(p, value):
    """stmtexpr : test"""
    emit_stmt(p, copy_loc(ast.Expr(value), value))

@rule
def p_typesuite(p, bindings_list=-1):
    """typesuite : skipnl typestmts"""
    if bindings_list and not isinstance(bindings_list[0], list):
        # We don't want a docstring to have location, because otherwise
        # CPython (debug) crashes with some lineno-related assertion failure.
        # That is why a builder is invoked directly, not through build_node.
        doc_builder, doc_loc = bindings_list.pop(0)
        doc_str = doc_builder()
    else:
        doc_str = ast.x_Const(None)

    bindings = list(itertools.chain.from_iterable(bindings_list))
    return doc_str, bindings


@rule  # target1: { ... }
def p_typestmt_namespace(p, qualname_wlocs=3, colons=4, body=-1):
    """typestmt : new_bblock nl_off qualname colons nl_on typebody"""
    bblock = pop_bblock(p)
    emit_stmt(p, *bblock.stmts)

    qualname, name_locs = map(tuple, zip(*qualname_wlocs))

    bindings = body[1]

    for binding in bindings:
        binding.qualname[:0] = qualname
        binding.name_locs[:0] = name_locs

    return bindings

@rule
def p_typestmt(p, qualname_colons=2):
    """typestmt : new_bblock binding"""
    bblock = pop_bblock(p)

    qualname_wlocs, colons = qualname_colons
    is_static = (colons == '::')

    func = bblock.fold_into_binding(is_static)

    qualname, name_locs = map(list, zip(*qualname_wlocs))
    binding_triple = Binding(qualname, name_locs,
                             func, ast.x_Const(is_static))
    return [binding_triple]

@rule  # metatype target(): { ... }
def p_binding_typedef(p, metatype_builders=2, qualname=3, mb_call_builder=4,
                      colons=5, body=-1):
    # Here qualname is used instead of pytest to work around
    # a reduce/reduce conflict with simple binding (pytest/qualname).
    """binding : nl_off qualname qualname mb_call colons nl_on typebody"""
    value = build_typedef(p, body, build_chain(metatype_builders),
                          qualname, mb_call_builder)
    emit_stmt(p, copy_loc(ast.Expr(value), value))
    return qualname, colons

@rule  # target1: ...
def p_binding_simple(p, qualname=2, colons=3):
    """binding : nl_off qualname colons nl_on stmtexpr"""
    return qualname, colons


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
def p_myatom_typedef(p, metatype, body):
    """myatom : pytest typebody"""
    return lambda: build_typedef(p, body, metatype)

@rule_wloc
def p_myatom_typedef_named(p, metatype, qualname, mb_call_builder, body):
    """myatom : pytest qualname mb_call typebody"""
    return lambda: build_typedef(p, body, metatype, qualname, mb_call_builder)


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

    return lambda expr: ast.x_Call(expr, args, keywords)

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
    return name

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
    qualname           :  name

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
    qualname           :  qualname        PERIOD     name

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

def my_parse(source, filename='<unknown>', mode='exec', **kwargs):
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


class MySyntaxError(Exception):
    """Stub class for using instead of standard SyntaxError because the latter
    has the special meaning for PLY.

    Constructor args are treated in the same way as for SyntaxError."""
