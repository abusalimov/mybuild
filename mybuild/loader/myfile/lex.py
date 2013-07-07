"""
Lexer definitions for My-files grammar.
"""

import ply.lex

# Derived from ANSI C example.

tokens = (
    # Literals (identifier, number, string)
    'ID', 'NUMBER', 'STRING',

    # Delimeters ( ) [ ] { } , . : =
    'LPAREN',   'RPAREN',
    'LBRACKET', 'RBRACKET',
    'LBRACE',   'RBRACE',
    'COMMA', 'PERIOD', 'COLON', 'EQUALS',
)

# Completely ignored characters
t_ignore           = ' \t\x0c'

# Newlines
def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# Delimeters
t_LPAREN           = r'\('
t_RPAREN           = r'\)'
t_LBRACKET         = r'\['
t_RBRACKET         = r'\]'
t_LBRACE           = r'\{'
t_RBRACE           = r'\}'
t_COMMA            = r','
t_PERIOD           = r'\.'
t_COLON            = r':'
t_EQUALS           = r'='

# Identifiers
t_ID               = r'[A-Za-z_][\w_]*'

# A regular expression rule with some action code
def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

# String literal
t_STRING = r'\"([^\\\n]|(\\.))*?\"'

# Comments
def t_comment(t):
    r'/\*(.|\n)*?\*/'
    t.lexer.lineno += t.value.count('\n')

def t_error(t):
    print("Illegal character %s" % repr(t.value[0]))
    t.lexer.skip(1)

lexer = ply.lex.lex(optimize=1, lextab=None)

if __name__ == "__main__":
    ply.lex.runmain(lexer)

