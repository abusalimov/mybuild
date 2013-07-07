from collections import namedtuple
from operator import itemgetter
import ply.yacc

from . import lex

from ...util.compat import *
from ...util.collections import OrderedDict


class Object(object):
    """docstring for Object"""

    def __init__(self, attrs, docstring, type_name=None, type_args=None,
                 name=None, scope_name=None):
        super(Object, self).__init__()

        self.attrs = attrs
        self.__doc__ = docstring

        self.type_name = type_name
        if type_args is None:
            type_args = {}
        self.type_args = type_args

        if name:
            self.__name__ = name
            if scope_name:
                self.__qualname__ = scope_name + '.' + name
            else:
                self.__qualname__ = name

    def __repr__(self):
        return '{type} {name}(**{type_args}) {attrs}'.format(
                    type=self.type_name,
                    name=getattr(self, '__qualname__', ''),
                    type_args=dict(self.type_args),
                    attrs=dict(self.attrs))


def to_rlist(reversed_list):
    return reversed_list[::-1]

def to_rdict(reversed_pairs):
    return OrderedDict(reversed(reversed_pairs))


tokens = lex.tokens
start = 'translation_unit'


def p_translation_unit(p):
    """translation_unit : values"""
    p[0] = p[1]


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
       value : object
       value : array"""
    p[0] = p[1]


def p_array(p):
    """array : LBRACKET values RBRACKET"""
    p[0] = to_rlist(p[2])


def p_object_0(p):
    """object : object_header
       object : object_header object_body"""
    type_name, name, type_args = p[1]
    attrs, docstring = p[2] if len(p) > 2 else ([], None)

    p[0] = Object(to_rdict(attrs), docstring, type_name, to_rdict(type_args),
                  name, scope_qualname(p))
    p.parser.scope_names.pop()

def p_object_1(p):
    """object : object_body"""
    p[0] = Object(*p[1])


def p_object_header_0(p):
    """object_header : qualname scope_name object_initializer"""
    p[0] = [p[1], p[2], p[3]]

def p_scope_name(p):
    """scope_name :
       scope_name : ID"""
    name = p[0] = p[1] if len(p) > 1 else None
    p.parser.scope_names.append(name)

def p_object_initializer(p):
    """object_initializer :
       object_initializer : LPAREN new_scope parameters RPAREN"""
    p[0] = to_rlist(p[3]) if len(p) > 1 else []
    p.parser.scope_depth -= 1

def p_new_scope(p):
    """new_scope :"""
    p.parser.scope_depth += 1

def scope_qualname(p):
    p = p.parser
    return '.'.join(name for name in p.scope_names[:p.scope_depth] if name)

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
    """object_body : LBRACE docstring object_members RBRACE"""
    p[0] = (to_rlist(p[3]), p[2])

def p_docstring_0(p):
    """docstring :
       docstring : STRING
       docstring : STRING COMMA"""
    if len(p) > 1:
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


def p_error(t):
    print("FUUUUUUUUUUUUUUUUUUUUUUUUUUUUU", t)


parser = ply.yacc.yacc(method='LALR', write_tables=False, debug=0)

def parse(text, **kwargs):
    parser.scope_names = []
    parser.scope_depth = 0
    return parser.parse(text, lexer=lex.lexer, **kwargs)

text = '''
[1],
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

}


'''

if __name__ == "__main__":
    import traceback, sys, code
    from pprint import pprint
    try:
        pprint(parse(text, debug=True))
    except:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        code.interact(local=ns)


