"""
PLY-based parser for Myfile grammar.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from _compat import *

import ast
import functools
import inspect
from functools import partial
import ply.yacc

from mylang import lex
from mylang.location import Fileinfo
from mylang.location import Location

from util.itertools import send_next_iter
from util.operator import getter


# Location tracking.

def node_loc(ast_node, p):
    return Location.from_ast_node(ast_node, p.lexer.fileinfo)

def ploc(p, i=1):
    return Location(p.lexer.fileinfo, p.lineno(i), p.lexpos(i))

def set_loc(ast_node, loc):
    return loc.init_ast_node(ast_node)

copy_loc = ast.copy_location


# Some utils.

class MySyntaxError(Exception):
    """Stub class for using instead of standard SyntaxError because the latter
    has the special meaning for PLY."""

    def __init__(self, msg, loc=None):
        loc_args = (loc.to_syntax_error_tuple(),) if loc is not None else ()
        super(MySyntaxError, self).__init__(msg, *loc_args)


def from_rlist(reversed_list, item=None):
    if item is not None:
        return list(map(getter[item], reversed(reversed_list)))
    else:
        return reversed_list[::-1]


# ast wrappers (py3k compat + arg defaults).

def _to_list(l=None):
    if l is None:
        l = []
    return l

def ast_name(name, ctx=None):
    if ctx is None:
        ctx = ast.Load()
    return ast.Name(name, ctx)

def ast_call(func, args=None, keywords=None, stararg=None, kwarg=None):
    return ast.Call(func, _to_list(args), _to_list(keywords), stararg, kwarg)

if py3k:
    def ast_arg(name):
        return ast.arg(name, None)
    ast_arg_name = getter.arg

    def ast_arguments(args=None, vararg=None, kwarg=None, defaults=None):
        return ast.arguments(_to_list(args), vararg, [], [], kwarg,
                             _to_list(defaults))

    def ast_funcdef(name, args, body):
        return ast.FunctionDef(name, args, body, [], None)

else:
    def ast_arg(name):
        return ast.Name(name, ast.Param())
    ast_arg_name = getter.id

    def ast_arguments(args=None, vararg=None, kwarg=None, defaults=None):
        return ast.arguments(_to_list(args), vararg, kwarg,
                             _to_list(defaults))

    def ast_funcdef(name, args, body):
        return ast.FunctionDef(name, args, body, [])


# p_func definition helpers.

def _rule_indices_from_argspec(func, with_p=True):
    args, _, _, defaults = inspect.getargspec(func)
    if with_p:
        if not args:
            raise TypeError("need at least 'p' argument")
        if defaults and len(defaults) == len(args):
            defaults = defaults[1:]
        args = args[1:]

    if defaults is not None:
        indices = list(range(1, len(args)-len(defaults)+1)) + list(defaults)
    else:
        indices = list(range(1, len(args)+1))

    return indices

def rule(func):
    indices = _rule_indices_from_argspec(func)
    @functools.wraps(func)
    def decorated(p):
        p[0] = func(p, *[p[i if i>=0 else len(p)+i] for i in indices])
    return decorated

def rule_wloc(func):
    indices = _rule_indices_from_argspec(func)
    @functools.wraps(func)
    def decorated(p):
        p[0] = (func(p, *[p[i if i>=0 else len(p)+i] for i in indices]),
                ploc(p))
    return decorated

def atom_func_wloc(func):
    indices = _rule_indices_from_argspec(func, with_p=False)
    @functools.wraps(func)
    def decorated(p):
        p[0] = (partial(func, *[p[i if i>=0 else len(p)+i] for i in indices]),
                ploc(p))
    return decorated


def alias_rule(index=1):
    def decorator(func):
        @functools.wraps(func)
        def decorated(p):
            p[0] = p[index + (index < 0 and len(p))]
        return decorated
    return decorator

def list_rule(item_index=1, list_index=-1):
    def decorator(func):
        @functools.wraps(func)
        def decorated(p):
            l = p[list_index + (list_index < 0 and len(p))]
            l.append(p[item_index])
            p[0] = l
        return decorated
    return decorator


# Here go grammar definitions for PLY.

tokens = lex.tokens


@rule
def p_exec_start(p, body=2):
    """exec_start : skipnl suite"""
    return ast.Module(body)

def p_skipnl(p):
    """skipnl :
       skipnl : NEWLINE"""

def p_new_suite(p):
    """new_suite :"""
    closures = []
    p.parser.suite_stack.append(closures)

@rule
def p_suite(p, stmts=2):
    """suite : new_suite listof_stmts"""
    stmts.reverse()
    closures = p.parser.suite_stack.pop()

    if closures:
        has_docstring = (stmts and
                         isinstance(stmts[0], ast.Expr) and
                         isinstance(stmts[0].value, ast.Str))
        # always leave a docstring (if any) first
        insert_idx = bool(has_docstring)

        stmts[insert_idx:insert_idx] = closures

    return stmts


@rule  # target1: target2 = ...
def p_stmt_binding(p, targets_value_pair):
    """stmt : listof_bindings"""
    targets, value = targets_value_pair
    if targets:
        targets.reverse()
        return copy_loc(ast.Assign(targets, value), targets[0])
    else:
        return copy_loc(ast.Expr(value), value)


@rule  # objtype name1: name2= { ... }
def p_stmt_objdef(p, objtype, targets_value_pair):
    """stmt : pytest listof_objdefs"""
    targets, closure = targets_value_pair
    targets.reverse()

    names = [ast.Str(target.id if isinstance(target, ast.Name) else
                     target.attr) for target in targets]

    # __maker(...) -> __objdef(objtype, [names], __maker, ...)
    closure.args[0:0] = [objtype, ast.List(names, ast.Load()), closure.func]
    closure.func = ast_name('__my_xobjdef__')

    return copy_loc(ast.Assign([ast.Tuple(targets, ast.Store())], closure),
                    targets[0])


@rule
def p_bindings_head(p, value):
    """listof_bindings : test"""
    return [], value

@rule
def p_objdefs_head(p, target, value):
    """listof_objdefs : objdef closure"""
    return [target], value

@rule
def p_xlist_tail(p, target, targets_value_pair):
    """listof_bindings : binding listof_bindings
       listof_objdefs :  objdef  listof_objdefs"""
    targets_value_pair[0].append(target)
    return targets_value_pair


def apply_trailer(trailer_wloc, expr=None):
    trailer, loc = trailer_wloc
    return loc.init_ast_node(trailer(expr) if expr is not None else trailer())

def fold_trailers(trailer_wlocs, expr=None):
    for trailer_wloc in reversed(trailer_wlocs):
        expr = apply_trailer(trailer_wloc, expr)

    return expr


def prepare_assignment(p, target):
    if not hasattr(target, 'ctx'):
        if isinstance(target, ast.Call):
            msg = "can't assign to function call"
        if isinstance(target, (ast.Num, ast.Str, ast.Dict)):
            msg = "can't assign to literal"
        else:
            msg = "can't assign to '{0}'".format(type(target))

        raise MySyntaxError(msg, node_loc(target, p))

    target.ctx = ast.Store()
    return target

def colon_assignment_target(p):
    selfarg_name = p.parser.selfarg_stack[-1]

    if selfarg_name is None:
        raise MySyntaxError("Object context assignment explicitly disabled",
                            ploc(p))

    return ast_name(selfarg_name)

@rule
def p_assing_colon(p, target_trailers):
    """binding : xattr_chain COLON
       objdef  : name_single COLON"""
    return prepare_assignment(p, fold_trailers(target_trailers,
                                               colon_assignment_target(p)))

@rule
def p_assign_equals(p, target):
    """binding : test EQUALS
       objdef  : name_apply EQUALS"""
    return prepare_assignment(p, target)

@rule
def p_name_single(p, name):
    """name_single : name"""
    return [name]
@rule
def p_name_apply(p, name):
    """name_apply : name"""
    return apply_trailer(name)


def fixup_closure_name(closure_maker, name):
    fn_node, ret_node = closure_maker.body
    fn_node.name = ret_node.value.id = name
    return closure_maker

@rule
def p_closure(p, argspec=2, stmts=3):
    """closure : LBRACE argspec suite RBRACE"""
    # Instead of defining it as usual:
    #   def closure(a, b=x, c=y):
    #       ...
    #
    # We have to wrap it by maker function to preserve semantics of evaluation
    # of default args and to prevent namespace pollution:
    #   def mk():
    #       def closure(a, b=x, c=y):
    #           ...
    #       closure.__name__
    #       return closure
    #   closure = mk()
    if not stmts:
        stmts.append(ast.Pass())  # otherwise all hell will break loose

    p.parser.selfarg_stack.pop()

    closures = p.parser.suite_stack[-1]

    fn_name = '<closure>'
    fn_node = ast_funcdef(fn_name, argspec, stmts)

    mk_name = '__my_closure_maker_{n}__'.format(n=len(closures))
    mk_body = [fn_node, ast.Return(ast_name(fn_name))]
    mk_node = ast_funcdef(mk_name, ast_arguments(), mk_body)

    closures.append(mk_node)

    return set_loc(ast_call(ast_name(mk_name)), ploc(p))

def p_nl_off(p):
    """nl_off :"""
    p.lexer.newline_stack[-1] += 1

def p_nl_on(p):
    """nl_on :"""
    p.lexer.newline_stack[-1] -= 1

@rule
def p_argspec(p, selfarg_name, argdefs=4):
    """argspec : selfarg nl_off PIPE argdefs nl_on PIPE mb_stmtdelim"""
    argdefault_pairs, (vararg, kwarg) = argdefs
    if selfarg_name is not None:
        selfarg = set_loc(ast_arg(selfarg_name), ploc(p))
        argdefault_pairs.append((selfarg, None))

    args = []
    defaults = []

    seen = set()  # of arg names

    for arg, default in reversed(argdefault_pairs):
        args.append(arg)
        if default is not None:
            defaults.append(default)

        elif defaults:
            raise MySyntaxError('non-default argument follows default '
                                'argument', node_loc(arg, p))
        name = ast_arg_name(arg)
        if name in seen:
            raise MySyntaxError("duplicate argument '{name}' in function "
                                "definition".format(**locals()),
                                node_loc(arg, p))
        else:
            seen.add(name)

    p.parser.selfarg_stack.append(selfarg_name)
    return ast_arguments(args, vararg, kwarg, defaults)

@rule
def p_argspec_empty(p, selfarg_name):
    """argspec : selfarg_default mb_stmtdelim
       argspec : selfarg_explicit stmtdelim"""
    if selfarg_name is not None:
        args = [set_loc(ast_arg(selfarg_name), ploc(p))]
    else:
        args = []

    p.parser.selfarg_stack.append(selfarg_name)
    return ast_arguments(args)

@alias_rule()
def p_selfarg_explicit(p):
    """selfarg : selfarg_default
       selfarg : selfarg_explicit"""

@rule
def p_selfarg_default(p):
    """selfarg_default :"""
    return 'self'

@alias_rule(-1)
def p_selfarg_explicit_name(p):
    """selfarg_explicit : COLON ID"""

def p_selfarg_explicit_none(p):
    """selfarg_explicit : COLON"""

@rule
def p_argdefs_init(p, starargs):
    """argdefs : argdefs_starargs"""
    return [], starargs

@rule
def p_argdefs_single(p, argdef, starargs):
    """argdefs : argdef no_starargs"""
    return [argdef], starargs

@rule
def p_argdefs_list(p, argdef, l_starargs_pair=-1):
    """argdefs : argdef COMMA argdefs"""
    l_starargs_pair[0].append(argdef)
    return l_starargs_pair

@rule
def p_argdefs_starargs_both(p, vararg, kwarg=-1):
    """argdefs_starargs : argdefs_vararg COMMA argdefs_kwarg"""
    return (vararg, kwarg)
@rule
def p_argdefs_starargs_vararg(p, vararg):
    """argdefs_starargs : argdefs_vararg"""
    return (vararg, None)
@rule
def p_argdefs_starargs_kwarg(p, kwarg):
    """argdefs_starargs : argdefs_kwarg"""
    return (None, kwarg)
@alias_rule()
def p_argdefs_starargs_none(p):
    """argdefs_starargs : no_starargs"""
@rule
def p_no_starargs(p):
    """no_starargs :"""
    return (None, None)

@alias_rule(2)
def p_argdefs_stararg(p):
    """argdefs_vararg : STAR       ID
       argdefs_kwarg  : DOUBLESTAR ID"""

@rule
def p_argdef(p, name, mb_default=-1):
    """argdef : ID EQUALS test
       argdef : ID"""
    if mb_default is name:
        mb_default = None
    return set_loc(ast_arg(name), ploc(p)), mb_default


@alias_rule()
def p_test(p):
    """test : pytest
       test : mytest"""

@rule
def p_xtest(p, trailers):
    """pytest : xattr_chain
       mytest : my_chain"""
    return fold_trailers(trailers)

@list_rule()
def p_xchain(p):
    """xattr_chain : pyatom listof_trailers
       xattr_chain : name   listof_trailers
       my_chain    : myatom listof_trailers"""


@atom_func_wloc
def p_myatom_closure(closure):
    """myatom : closure"""
    return closure

@atom_func_wloc
def p_myatom(objtype, mb_name, closure=-1):
    """myatom : pytest closure
       myatom : pytest ID closure"""
    if mb_name is closure:
        mb_name = '<unnamed>'

    closure.args[0:0] = [objtype, ast.Str(mb_name), closure.func]
    closure.func = ast_name('__my_objdef__')

    return closure


@atom_func_wloc
def p_pyatom_num(n):
    """pyatom : NUMBER"""
    return ast.Num(n)

@atom_func_wloc
def p_pyatom_str(s):
    """pyatom : STRING"""
    return ast.Str(s)

@atom_func_wloc
def p_pyatom_list(testlist=2):  # [item, ...]
    """pyatom : LBRACKET testlist RBRACKET"""
    return ast.List(from_rlist(testlist[0]), ast.Load())

@atom_func_wloc
def p_pyatom_dict(kv_pairs=2):  # [key: value, ...]
    """pyatom : LBRACKET listof_dictents RBRACKET"""
    keys   = from_rlist(kv_pairs, 0)
    values = from_rlist(kv_pairs, 1)

    return ast.Dict(keys, values)

@rule
def p_dictent(p, key, value=3):
    """dictent : test COLON test"""
    return key, value

@atom_func_wloc
def p_pyatom_tuple(testlist=2):  # (item, ...)
    """pyatom : LPAREN testlist RPAREN"""
    test_l, test_el = testlist
    if test_el is not None:
        return test_el
    else:
        return ast.Tuple(from_rlist(test_l), ast.Load())

@rule_wloc
def p_trailer_call(p, kw_arg_pairs=2):  # x(arg, kw=arg, ...)
    """trailer : LPAREN listof_arguments RPAREN"""
    pair_it = send_next_iter(reversed(kw_arg_pairs))

    args = []   # positional arguments
    for kw_wloc, arg in pair_it:
        if kw_wloc is not None:
            pair_it.send((kw_wloc, arg))
            break
        args.append(arg)

    keywords = []   # keyword arguments
    seen = set()
    for kw_wloc, arg in pair_it:
        if kw_wloc is None:
            raise MySyntaxError('non-keyword arg after keyword arg',
                                node_loc(arg, p))
        kw, loc = kw_wloc
        if kw in seen:
            raise MySyntaxError('keyword argument repeated', loc)
        else:
            seen.add(kw)
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
def p_trailer_attr_or_name(p, name=-1):  # x.attr
    """trailer : PERIOD ID
       name    : ID"""
    def trailer(expr=None):
        if expr is not None:
            return ast.Attribute(expr, name, ast.Load())
        else:
            return ast_name(name)
    return trailer


@rule_wloc
def p_trailer_item(p, item=2):  # x[item]
    """trailer : LBRACKET test RBRACKET"""
    return lambda expr: ast.Subscript(expr, ast.Index(item), ast.Load())


def p_trailer_multigetter(p):  # x.[attr, [item], (call), ...]
    """trailer : PERIOD LBRACKET listof_getters RBRACKET"""
    raise NotImplementedError

def p_getter(p):
    """getter : xattr_chain"""
    raise NotImplementedError

def p_trailer_multisetter(p):  # x.[attr: value, [item]: value, ...]
    """trailer : PERIOD LBRACKET listof_setters RBRACKET"""
    raise NotImplementedError

def p_setter(p):
    """setter : xattr_chain COLON test"""
    raise NotImplementedError


# testlist is a pair of [list of elements] and a single element (if any)

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


# generic (possibly comma-separated, and with trailing comma) list parsing

def p_list(p):
    """
    listof_stmts :
    listof_trailers :
    listof_arguments :
    listof_getters :
    """
    p[0] = []

def p_list_head(p):
    """
    listof_stmts :        stmt
    listof_arguments :    argument
    listof_dictents :     dictent
    listof_dictents :     dictent COMMA
    listof_setters :      setter
    listof_setters :      setter COMMA
    listof_getters :      getter
    """
    p[0] = [p[1]]

@list_rule()
def p_list_tail(p):
    """
    listof_stmts :        stmt   stmtdelim listof_stmts
    listof_trailers :     trailer          listof_trailers
    listof_arguments :    argument   COMMA listof_arguments
    listof_dictents :     dictent    COMMA listof_dictents
    listof_getters :      getter     COMMA listof_getters
    listof_setters :      setter     COMMA listof_setters
    """

def p_stmtdelim(p):
    """stmtdelim : NEWLINE
       stmtdelim : SEMI skipnl"""

def p_mb_stmtdelim(p):
    """mb_stmtdelim :
       mb_stmtdelim : stmtdelim"""

def p_error(t):
    if t is not None:
        raise MySyntaxError("Unexpected {0!r} token".format(t.value),
                            lex.loc(t))
    else:
        raise MySyntaxError("Premature end of file")


parser = ply.yacc.yacc(start='exec_start',
                       write_tables=False,
                       debug=False,
                       errorlog=ply.yacc.NullLogger())

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

    p.suite_stack = []
    p.selfarg_stack = ['__my_module__']

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
    {}
    {;}
    {:;}
    {:slf;}
    {:||}
    {|arg|}
    {|arg|;}
    {:|arg={foo:bar}|}
    {:slf|arg|}

    module() foo: bar= {
        foo: [cc]
        files: ["foo.c"]
    }
    """
    from mako._ast_util import SourceGenerator as SG

    def pr(node):
        sg=SG('    ')
        sg.visit(node)
        return ''.join(sg.result)

    ast_root = parse(source, debug=0)

    compile(ast_root, "", 'exec')
    print(pr(ast.parse("def foo(a, *v, **kw): pass", mode='exec')))
    print(pr(ast_root))
    print(ast.dump(ast_root))

