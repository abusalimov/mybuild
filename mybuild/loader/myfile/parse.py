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


def p_array(p):
    """array : LBRACKET values RBRACKET"""
    p[0] = to_rlist(p[2])


def p_new_object(p):
    """new_object :"""
    p[0] = push_object(p, Object(scope_object(p)))

def p_init_object(p):
    """init_object : object_header
       init_object : object_header object_body
       init_object : object_body"""
    pop_object(p)


def p_object_header(p):
    """object_header : qualname object_name object_args"""
    # need to set a name prior to entering object body
    this  = this_object(p)
    this.init_header(ref_name=p[1], args=to_rdict(p[3]), name=p[2])

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
    """object_body : LBRACE enter_scope docstring object_members RBRACE"""
    this_object(p).init_body(attrs=to_rdict(p[4]), docstring=p[3])
    leave_scope(p)

def p_enter_scope(p):
    """enter_scope :"""
    enter_scope(p)


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

class Object(object):
    """docstring for Object"""

    def __init__(self, parent=None):
        super(Object, self).__init__()
        if parent is not None:
            if not parent.name:
                parent = parent.scope
            assert parent.name
        self.scope = parent

        self.ref        = None
        self.ref_name   = None
        self.ref_getter = None
        self.referrers  = []  # updated upon resolving links to this object

        self.args     = []
        self.name     = None
        self.qualname = None

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
        self.name = self.qualname = name

        if name:
            scope = self.scope
            if scope is not None and scope.qualname:
                self.qualname = scope.qualname + '.' + name

    def init_body(self, attrs, docstring):
        self.attrs     = attrs
        self.docstring = docstring

    def link_local(self, local_exports):
        if self.ref_name:
            self.ref = self.resolve_local_ref(local_exports, self.ref_name)

    def resolve_local_ref(self, local_exports, lookup_name):
        for scope in self.iter_scope_chain():
            try:
                return local_exports[scope.qualname + '.' + lookup_name]
            except KeyError:
                pass
        return local_exports.get(lookup_name)

    def iter_scope_chain(self):
        s = self.scope
        while s is not None:
            yield s
            s = s.scope

    def __repr__(self):
        return '{ref_name} {name}({args}){attrs}'.format(
                    ref_name=self.ref_name or '',
                    name=self.qualname or '',
                    args=dict(self.args) or '',
                    attrs=dict(self.attrs) or '')


def to_rlist(reversed_list):
    return reversed_list[::-1]

def to_rdict(reversed_pairs):
    return OrderedDict(reversed(reversed_pairs))


def this_object(p):
    return p.parser.object_stack[-1]
def scope_object(p):
    return p.parser.object_stack[p.parser.nesting_depth]

def push_object(p, o):
    p.parser.objects.add(o)  # also remember it in a global set
    p.parser.object_stack.append(o)
    return o
def pop_object(p):
    return p.parser.object_stack.pop()

def enter_scope(p):
    p.parser.nesting_depth += 1
def leave_scope(p):
    p.parser.nesting_depth -= 1


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

    objects = parser.objects = set()

    parser.object_stack  = [None]
    parser.nesting_depth = 0

    result = parser.parse(text, lexer=lex.lexer, **kwargs)

    export_pairs = list((o.qualname, o) for o in objects if o.qualname)
    exports = dict(export_pairs)

    if len(exports) != len(export_pairs):
        raise  # Multiple definition.

    for o in objects:
        o.link_local(exports)
        print o.ref_name, ' -> ', o.ref

    unresolved = list(o for o in objects if o.ref_name and not o.ref)

    return (result, exports, unresolved)


text = '''
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


