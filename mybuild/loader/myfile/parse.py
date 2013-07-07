from collections import namedtuple
from operator import itemgetter
import ply.yacc

from . import lex

from ...util.compat import *
from ...util.collections import OrderedDict


class Object(object):
    """docstring for Object"""

    def __init__(self, parent=None):
        super(Object, self).__init__()
        self.parent = parent

        self.init_header(None, {})
        self.init_body({}, None)

    def init_header(self, type_name, type_args, name=None):
        self.type_name = type_name
        self.type_args = type_args
        self.__name__ = self.__qualname__ = name
        if name and self.parent and self.parent.__qualname__:
            self.__qualname__ = self.parent.__qualname__ + '.' + name

    def init_body(self, attrs, docstring):
        self.attrs = attrs
        self.__doc__ = docstring

    def __repr__(self):
        return '{type} {name}({type_args}){attrs}'.format(
                    type=self.type_name or '',
                    name=self.__qualname__ or '',
                    type_args=dict(self.type_args) or '',
                    attrs=dict(self.attrs) or '')


def to_rlist(reversed_list):
    return reversed_list[::-1]

def to_rdict(reversed_pairs):
    return OrderedDict(reversed(reversed_pairs))


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
    p[0] = push_scope(p, Object(parent_scope(p)))

def p_init_object(p):
    """init_object : object_header
       init_object : object_header object_body
       init_object : object_body"""
    pop_scope(p)


def p_object_header(p):
    """object_header : qualname object_name object_args"""
    # need to set a name prior to entering object body
    cur_scope(p).init_header(type_name=p[1], type_args=to_rdict(p[3]), name=p[2])

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
    cur_scope(p).init_body(attrs=to_rdict(p[4]), docstring=p[3])
    p.parser.nesting_depth -= 1

def p_enter_scope(p):
    """enter_scope :"""
    p.parser.nesting_depth += 1

def parent_scope(p):
    return p.parser.scope_objects[p.parser.nesting_depth]

def cur_scope(p):
    return p.parser.scope_objects[-1]

def push_scope(p, o):
    p.parser.scope_objects.append(o)
    return o

def pop_scope(p):
    return p.parser.scope_objects.pop()


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


def parse(text, **kwargs):
    parser.exports    = {}  # {qualname: object}
    parser.references = []  # (name, scope)

    parser.scope_objects = [None]
    parser.nesting_depth = 0

    return parser.parse(text, lexer=lex.lexer, **kwargs)


text = '''
module Kernel(debug = False) {
    "Docstring!"

    x: xxx xname() {},

    source: "init.c",

    depends: [
        embox.arch./*[
            libarch,
            locore,
            */cpu(endian="be")/*,
        ] */{runtime: False},

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


