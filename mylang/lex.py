"""
Lexer definitions for My-files grammar.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from _compat import *

import ply.lex

from mylang.location import Location


def loc(t):
    try:
        fileinfo = t.lexer.fileinfo
    except AttributeError:
        pass
    else:
        return Location(fileinfo, t.lineno, t.lexpos)


# Derived from ANSI C example.

tokens = (
    # Literals (identifier, number, string)
    'ID', 'NUMBER', 'STRING',

    # Delimeters ( ) [ ] { } , . : $ = ; |
    'LPAREN',   'RPAREN',
    'LBRACKET', 'RBRACKET',
    'LBRACE',   'RBRACE',
    'COMMA', 'PERIOD', 'COLON', 'EQUALS', 'SEMI', 'PIPE', 'STAR', 'DOUBLESTAR',

    # Logical newline
    'NEWLINE',
)

# Completely ignored characters
t_ignore           = ' \t\x0c'

# Newlines
def t_NEWLINE(t):
    r'\n*((/\*(.|\n)*?\*/)|((//.*)?\n))\n*'
    n_newlines = t.value.count('\n')
    t.lexer.lineno += n_newlines
    if n_newlines and not t.lexer.newline_stack[-1]:
        return t


# Paren/bracket counting
def t_LPAREN(t):   r'\('; t.lexer.newline_stack[-1] += 1;  return t
def t_RPAREN(t):   r'\)'; t.lexer.newline_stack[-1] -= 1;  return t
def t_LBRACKET(t): r'\['; t.lexer.newline_stack[-1] += 1;  return t
def t_RBRACKET(t): r'\]'; t.lexer.newline_stack[-1] -= 1;  return t
def t_LBRACE(t):   r'\{'; t.lexer.newline_stack.append(0); return t
def t_RBRACE(t):   r'\}'; t.lexer.newline_stack.pop();     return t

# Delimeters
t_COMMA            = r','
t_PERIOD           = r'\.'
t_COLON            = r':'
t_EQUALS           = r'='
t_SEMI             = r';'
t_PIPE             = r'\|'
t_STAR             = r'\*'
t_DOUBLESTAR       = r'\*\*'

# Identifiers
t_ID               = r'[A-Za-z_][\w_]*'

# A regular expression rule with some action code
def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

# String literal
def t_STRING(t):
    r'\"([^\\\n]|(\\.))*?\"'
    t.value = t.value[1:-1]
    return t

def t_error(t):
    raise SyntaxError("Illegal character {0!r}".format(t.value[0]),
                      loc(t).to_syntax_error_tuple())


lexer = ply.lex.lex(optimize=1, lextab=None)
lexer.newline_stack = [0]

if __name__ == "__main__":
    ply.lex.runmain(lexer)

