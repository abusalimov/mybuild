"""
PLY-based parser for My-files grammar. Also provides some scoping features.
"""

import ply.yacc
from operator import attrgetter

from . import lex

from ...util import cached_property
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
    p.parser.objects.add(pop_object(p))


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


class LinkageError(Exception):
    pass

class UnresolvedReferenceError(LinkageError, NameError):
    pass

class UnresolvedAttributeError(LinkageError, AttributeError):
    pass


class MyfileDeclarative(object):
    """docstring for MyfileDeclarative"""

    def my_getattr(self, attr):
        return getattr(self, attr)


class Stub(object):
    """docstring for Stub"""

    def __init__(self, name=None):
        super(Stub, self).__init__()
        self.name    = name

        self.resolve_hooks = []  # updated upon resolving links to this object

    def resolve_to(self, payload):
        for hook in self.resolve_hooks:
            hook(payload)


class ObjectStub(Stub, MyfileDeclarative):
    """docstring for ObjectStub"""

    @cached_property
    def type_root(self):
        try:
            return self.scope[self.type_name]
        except KeyError:
            raise UnresolvedReferenceError("name '%s' is not defined" %
                                           self.type_name)

    @cached_property
    def type_or_stub(self):
        """Reference to a resolved type (ObjectStub)."""
        ret = self.type_root

        try:
            for attr in self.type_attrs:
                if isinstance(ret, MyfileDeclarative):
                    ret = ret.my_getattr(attr)
                else:
                    ret = getattr(ret, attr)

        except AttributeError as e:
            raise UnresolvedAttributeError(*e.args)

        if isinstance(ret, Stub):
            def resolve(payload):
                self.type_or_stub = payload
            ret.resolve_hooks.append(resolve)

        return ret

    def __init__(self, scope=None, parent=None):
        super(ObjectStub, self).__init__()
        self.scope = scope

        if parent is not None:
            if not parent.name:
                parent = parent.named_parent
            assert parent.name
        self.named_parent = parent

        self.type_name = None  # qualified name of a type

        self.args   = []  # positional type arguments TODO unused
        self.kwargs = {}  # keyword type arguments

        self.attrs     = []
        self.docstring = None

    def init_header(self, type_name, kwargs, name=None):
        name_frags = type_name.split('.') if type_name else [None]
        self.type_name  = name_frags[0]
        self.type_attrs = name_frags[1:]

        self.kwargs = kwargs
        self.name   = name

        if name:
            self.named_children = {}
            self.scope[name] = self
            parent = self.named_parent
            if parent is not None:
                parent.named_children[name] = self

    def init_body(self, attrs, docstring):
        self.attrs     = attrs
        self.docstring = docstring

    def my_getattr(self, attr):
        try:
            return self.named_children[attr]
        except KeyError:
            raise AttributeError  # TODO think about it

    def __repr__(self):
        return '{type_name} in ({scope}) {name}({kwargs}){attrs}'.format(
                    type_name='.'.join([self.type_name] + self.type_attrs)
                        if self.type_name else '',
                    scope=self.scope,
                    name=self.name or '',
                    kwargs=dict(self.kwargs) or '',
                    attrs=dict(self.attrs) or '')


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


    builtin_scope = DictScope(builtins)
    builtin_scope.setdefault(None, dict)  # objects with no type info ({})

    global_scope = ObjectScope(parent=builtin_scope)

    parser.scope_stack   = [global_scope]
    parser.object_stack  = [None]

    objects = parser.objects = set()

    result = parser.parse(text, lexer=lex.lexer, **kwargs)

    unresolved = list()
    for o in objects:
        try:
            print o.type_name, ' -> ', o.type_or_stub
        except LinkageError as e:
            unresolved.append(o)
            print e

    return (result, dict(global_scope), unresolved)


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

    try:
        pprint(parse(text, builtins=get_builtins(), debug=0))
    except:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        code.interact(local=ns)


