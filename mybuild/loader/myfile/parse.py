"""
PLY-based parser for My-files grammar. Also provides some scoping features.
"""

import ply.yacc
from operator import attrgetter

from . import lex
from .linkage import BuiltinScope
from .linkage import ObjectScope
from .linkage import ObjectStub

from ...util import singleton
from ...util.collections import OrderedDict
from ...util.compat import *


tokens = lex.tokens
start = 'translation_unit'


def p_translation_unit(p):
    """translation_unit : values"""
    p[0] = to_rlist(p[1])


def p_values_0(p):
    """values :
       values : value"""
    p[0] = [p[1]] if len(p) > 1 else []
def p_values_1(p):
    """values : value COMMA values"""
    l = p[0] = p[3]
    l.append(p[1])

def p_value(p):
    """value : STRING
       value : NUMBER
       value : new_object init_object
       value : array"""
    p[0] = p[1]


def p_new_object(p):
    """new_object :"""
    p[0] = push_object(p, ObjectStub(this_scope(p), this_scope_object(p)))

def p_init_object(p):
    """init_object : object_header
       init_object : object_header object_body
       init_object : object_body"""
    p.parser.linker.all_objects.append(pop_object(p))


def p_object_header(p):
    """object_header : qualname object_name object_args"""
    this_object(p).init_header(type_name=p[1], name=p[2],
                               kwargs=to_rdict(p[3]))

def p_object_name(p):
    """object_name : empty
       object_name : ID"""
    p[0] = p[1]

def p_object_args(p):
    """object_args :
       object_args : LPAREN parameters RPAREN"""
    p[0] = to_rlist(p[2]) if len(p) > 1 else []


def p_parameters_0(p):
    """parameters :
       parameters : parameter"""
    p[0] = [p[1]] if len(p) > 1 else []
def p_parameters_1(p):
    """parameters : parameter COMMA parameters"""
    l = p[0] = p[3]
    l.append(p[1])

def p_parameter(p):
    """parameter : ID EQUALS value"""
    p[0] = (p[1], p[3])


def p_object_body(p):
    """object_body : LBRACE new_scope docstring object_members RBRACE"""
    this_object(p).init_body(attrs=to_rdict(p[4]), docstring=p[3])
    p.parser.linker.all_scopes.append(pop_scope(p))

def p_new_scope(p):
    """new_scope :"""
    push_scope(p, ObjectScope(this_scope(p)))


def p_docstring_0(p):
    """docstring : empty
       docstring : STRING
       docstring : STRING COMMA"""
    p[0] = p[1]

def p_object_members_0(p):
    """object_members :
       object_members : object_member"""
    p[0] = [p[1]] if len(p) > 1 else []
def p_object_members_1(p):
    """object_members : object_member COMMA object_members"""
    l = p[0] = p[3]
    l.append(p[1])

def p_object_member(p):
    """object_member : string_or_qualname COLON value"""
    p[0] = (p[1], p[3])


def p_array(p):
    """array : LBRACKET values RBRACKET"""
    p[0] = to_rlist(p[2])


def p_qualname_0(p):
    """qualname : ID"""
    p[0] = p[1]
def p_qualname_1(p):
    """qualname : ID PERIOD qualname"""
    p[0] = p[1] + """.""" + p[3]


def p_string_or_qualname_0(p):
    """string_or_qualname : STRING
       string_or_qualname : qualname"""
    p[0] = p[1]


def p_empty(p):
    """empty : """
    pass

def p_error(t):
    print("FUUUUUUUUUUUUUUUUUUUUUUUUUUUUU", t)


parser = ply.yacc.yacc(method='LALR', write_tables=False, debug=0)


# Here go scoping-related stuff + some utils.


def to_rlist(reversed_list):
    return reversed_list[::-1]

def to_rdict(reversed_pairs):
    return OrderedDict(reversed(reversed_pairs))


def this_scope(p):  return p.parser.scope_stack[-1]
def this_object(p): return p.parser.object_stack[-1]

def this_scope_object(p):
    return p.parser.object_stack[len(p.parser.scope_stack)-1]

def push_scope(p, scope): p.parser.scope_stack.append(scope); return scope
def pop_scope(p):  return p.parser.scope_stack.pop()

def push_object(p, obj):  p.parser.object_stack.append(obj); return obj
def pop_object(p): return p.parser.object_stack.pop()


# The main entry point.

def parse(text, linker, builtins={}, **kwargs):
    """
    Parses the given text and returns the result.

    Args:
        text (str) - data to parse
        builtins (dict) - builtin variables
        **kwargs are passed directly to the underlying PLY parser

    Returns:
        a tuple (ast_root, global_scope).

    Note:
        This function is NOT reentrant.
    """

    global_scope = ObjectScope(parent=BuiltinScope(builtins))

    parser.scope_stack   = [global_scope]
    parser.object_stack  = [None]

    parser.linker = linker

    ast_root = parser.parse(text, lexer=lex.lexer, **kwargs)

    parser.linker.all_scopes.append(global_scope)

    return (ast_root, dict(global_scope))


text = '''
module Kernel(debug = False) {
    "Docstring!"

    x: xxx xname() {},

    source: "init.c",

    depends: [
        embox.arch.cpu(endian="be"){runtime: False},

        embox.driver.diag.diag_api,
    ],
    depends: embox.kernel.stack,

},


'''

if __name__ == "__main__":
    from .linkage import GlobalLinker, LocalLinker
    import traceback, sys, code
    from pprint import pprint

    def get_builtins():
        @singleton
        class embox(object):
            def __getattr__(self, attr):
                return self
        class module(object):
            pass
        xxx = 42

        return dict(locals(), **{
                        'None':  None,
                        'True':  True,
                        'False': False,
                    })

    gl = GlobalLinker()
    ll = LocalLinker(gl)
    try:
        pprint(parse(text, linker=ll, builtins=get_builtins()))
    except:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        code.interact(local=ns)


