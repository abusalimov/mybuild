"""
PLY-based parser for My-files grammar. Also provides some scoping features.
"""

import ply.yacc
from operator import attrgetter

from . import lex

from ...util import identity
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
    p[0] = push_object(p, Object(this_scope(p)))

def p_init_object(p):
    """init_object : object_header
       init_object : object_header object_body
       init_object : object_body"""
    p.parser.objects.add(pop_object(p))


def p_object_header(p):
    """object_header : qualname object_name object_args"""
    this_object(p).init_header(ref_name=p[1], args=to_rdict(p[3]), name=p[2])

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
    pop_scope(p)

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

class Scope(object):
    def __getitem__(self, name):
        raise KeyError
    def __repr__(self):
        return type(self).__name__.join('<>')

class MutableScope(Scope):
    def __setitem__(self, name, value):
        pass


class DelegatingScope(Scope):
    """docstring for DelegatingScope"""

    def __init__(self, parent=Scope()):
        super(DelegatingScope, self).__init__()
        self.parent = parent

    def __missing__(self, key):
        return self.parent[key]

    def __repr__(self):
        return '%s -> %r' % (super(DelegatingScope, self).__repr__(),
                             self.parent)


class DictScope(dict, MutableScope):
    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, list(self))


class ConflictsAwareDictScope(DictScope):
    """Stores conflicting items detected upon setting a value for an existing
    name."""

    def __init__(self):
        super(ConflictsAwareDictScope, self).__init__()
        self.conflicts = dict()    # {name: [values]}

    def __setitem__(self, name, value):
        if name not in self.conflicts:
            if name in self:
                del self[name]
            else:
                super(ConflictsAwareDictScope, self).__setitem__(name, value)
                return  # hot path

            self.conflicts[name] = [old_value]
        self.conflicts[name].append(value)


class ObjectScope(DelegatingScope, ConflictsAwareDictScope):
    pass


class Object(object):
    """docstring for Object"""

    def __init__(self, scope=None):
        super(Object, self).__init__()
        self.scope = scope

        self.ref        = None
        self.ref_name   = None
        self.ref_getter = None
        self.referrers  = []  # updated upon resolving links to this object

        self.args     = []
        self.name     = None

        self.attrs     = []
        self.docstring = None

    def init_header(self, ref_name, args, name=None):
        self.ref_name   = ref_name
        self.ref_getter = identity

        if ref_name:
            self.ref_name, _, ref_attr = ref_name.partition('.')
            if ref_attr:
                self.ref_getter = attrgetter(ref_attr)

        self.args = args
        self.name = name

        if name:
            self.scope[name] = self

    def init_body(self, attrs, docstring):
        self.attrs     = attrs
        self.docstring = docstring

    def link_local(self):
        if self.ref_name:
            try:
                self.ref = self.scope[self.ref_name]
            except KeyError:
                pass

    def __repr__(self):
        return '{ref_name} in ({scope}) {name}({args}){attrs}'.format(
                    ref_name=self.ref_name or '',
                    scope=self.scope,
                    name=self.name or '',
                    args=dict(self.args) or '',
                    attrs=dict(self.attrs) or '')


def to_rlist(reversed_list):
    return reversed_list[::-1]

def to_rdict(reversed_pairs):
    return OrderedDict(reversed(reversed_pairs))


def this_scope(p):  return p.parser.scope_stack[-1]
def this_object(p): return p.parser.object_stack[-1]

def push_scope(p, scope): p.parser.scope_stack.append(scope); return scope
def pop_scope(p):  return p.parser.scope_stack.pop()

def push_object(p, obj):  p.parser.object_stack.append(obj); return obj
def pop_object(p): return p.parser.object_stack.pop()


# The main entry point.

def parse(text, builtins={}, **kwargs):
    """
    Parses the given text and returns the result.

    Args:
        text (str) - data to parse
        builtins (dict) - builtin variables
        **kwargs are passed directly to the underlying PLY parser

    Returns a tuple (AST root, exports, unresolved):
      - AST root is always a list of values
      - exports is a dict mapping qualified names to corresponding objects
      - unresolved is a list of objects with unresolved references
    """

    global_scope = ObjectScope(parent=DictScope(builtins))

    parser.scope_stack   = [global_scope]
    parser.object_stack  = [None]

    objects = parser.objects = set()

    result = parser.parse(text, lexer=lex.lexer, **kwargs)

    for o in objects:
        o.link_local()
        print o.ref_name, ' -> ', o.ref

    unresolved = list(o for o in objects if o.ref_name and not o.ref)

    return (result, dict(global_scope), unresolved)


text = '''
obj obj,
obj module,
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

x xxx {
    a: {
        aa: z zzz {

        },
        b: sss
    },
    c: r rrr {
        d: bb bbb,
    }
}


'''

if __name__ == "__main__":
    import traceback, sys, code
    from pprint import pprint
    try:
        pprint(parse(text, debug=0))
    except:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        code.interact(local=ns)


