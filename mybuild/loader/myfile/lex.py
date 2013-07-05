"""
Lexer definitions for My-files grammar.
"""

import ply.lex

# Derived from ANSI C example.

# Reserved words
reserved = (
    'ABSTRACT',
    'ANNOTATION',
    'BOOLEAN',
    'DEPENDS',
    'EXTENDS',
    'FEATURE',
    'IMPORT',
    'INTERFACE',
    'MODULE',
    'NUMBER',
    'OBJECT',
    'OPTION',
    'PACKAGE',
    'PROVIDES',
    'REQUIRES',
    'SOURCE',
    'STATIC',
    'STRING',
)

tokens = reserved + (
    # Literals (identifier, number, string)
    'ID', 'NUMBER_LITERAL', 'STRING_LITERAL',

    # Operators (+,-,*,/,%,|,&,~,^,<<,>>, ||, &&, !, <, <=, >, >=, ==, !=)
    # 'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MOD',
    # 'OR', 'AND', 'NOT', 'XOR', 'LSHIFT', 'RSHIFT',
    # 'LOR', 'LAND', 'LNOT',
    # 'LT', 'LE', 'GT', 'GE', 'EQ', 'NE',

    # Assignment (=, *=, /=, %=, +=, -=, <<=, >>=, &=, ^=, |=)
    'EQUALS',
    # 'TIMESEQUAL', 'DIVEQUAL', 'MODEQUAL', 'PLUSEQUAL', 'MINUSEQUAL',
    # 'LSHIFTEQUAL','RSHIFTEQUAL', 'ANDEQUAL', 'XOREQUAL', 'OREQUAL',

    # Delimeters ( ) [ ] { } , . :
    'LPAREN', 'RPAREN',
    'LBRACKET', 'RBRACKET',
    'LBRACE', 'RBRACE',
    'COMMA', 'PERIOD', 'COLON',

    # At sign: @
    'AT',

    'WILDCARD',
)

# Completely ignored characters
t_ignore           = ' \t\x0c'

# Newlines
def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n")

# Operators
# t_PLUS             = r'\+'
# t_MINUS            = r'-'
# t_TIMES            = r'\*'
# t_DIVIDE           = r'/'
# t_MOD              = r'%'
# t_OR               = r'\|'
# t_AND              = r'&'
# t_NOT              = r'~'
# t_XOR              = r'\^'
# t_LSHIFT           = r'<<'
# t_RSHIFT           = r'>>'
# t_LOR              = r'\|\|'
# t_LAND             = r'&&'
# t_LNOT             = r'!'
# t_LT               = r'<'
# t_GT               = r'>'
# t_LE               = r'<='
# t_GE               = r'>='
# t_EQ               = r'=='
# t_NE               = r'!='

# Assignment operators

t_EQUALS           = r'='
# t_TIMESEQUAL       = r'\*='
# t_DIVEQUAL         = r'/='
# t_MODEQUAL         = r'%='
# t_PLUSEQUAL        = r'\+='
# t_MINUSEQUAL       = r'-='
# t_LSHIFTEQUAL      = r'<<='
# t_RSHIFTEQUAL      = r'>>='
# t_ANDEQUAL         = r'&='
# t_OREQUAL          = r'\|='
# t_XOREQUAL         = r'^='

# Delimeters
t_LPAREN           = r'\('
t_RPAREN           = r'\)'
t_LBRACKET         = r'\['
t_RBRACKET         = r'\]'
t_LBRACE           = r'\{'
t_RBRACE           = r'\}'
t_COMMA            = r','
t_WILDCARD         = r'\.\*'
t_PERIOD           = r'\.'
t_COLON            = r':'
t_AT               = r'@'

# Identifiers and reserved words

reserved_map = dict((r.lower(), r) for r in reserved)

def t_ID(t):
    r'[A-Za-z_][\w_]*'
    t.type = reserved_map.get(t.value, "ID")
    return t

# Integer literal
t_NUMBER_LITERAL = r'\d+'

# String literal
t_STRING_LITERAL = r'\"([^\\\n]|(\\.))*?\"'

# Comments
def t_comment(t):
    r'/\*(.|\n)*?\*/'
    t.lexer.lineno += t.value.count('\n')

def t_error(t):
    print("Illegal character %s" % repr(t.value[0]))
    t.lexer.skip(1)

lexer = ply.lex.lex(optimize=1)

if __name__ == "__main__":
    ply.lex.runmain(lexer)

