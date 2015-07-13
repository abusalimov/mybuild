"""
Lexer definitions for My-files grammar.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from mybuild._compat import *

import ply.lex

from mybuild.lang.location import Location


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
    'COMMA', 'PERIOD', 'COLON', 'DOUBLECOLON', 'EQUALS', 'SEMI',

    # Logical newline
    'NEWLINE',
)

# Completely ignored characters
t_ignore           = ' \t'
t_ignore_COMMENT   = r'//.*'

# Newlines (including block comments)
def t_NEWLINE(t):
    r'(\n|/\*(.|\n)*?\*/)+'
    nr_newlines = t.value.count('\n')
    t.lexer.lineno += nr_newlines
    if nr_newlines and not t.lexer.ignore_newline_stack[-1]:
        return t


# Paren/bracket counting
def t_LPAREN(t):   r'\('; t.lexer.ignore_newline_stack[-1] += 1;  return t
def t_RPAREN(t):   r'\)'; t.lexer.ignore_newline_stack[-1] -= 1;  return t
def t_LBRACKET(t): r'\['; t.lexer.ignore_newline_stack[-1] += 1;  return t
def t_RBRACKET(t): r'\]'; t.lexer.ignore_newline_stack[-1] -= 1;  return t
def t_LBRACE(t):   r'\{'; t.lexer.ignore_newline_stack.append(0); return t
def t_RBRACE(t):   r'\}'; t.lexer.ignore_newline_stack.pop();     return t

# Delimeters
t_COMMA            = r','
t_PERIOD           = r'\.'
t_COLON            = r':'
t_DOUBLECOLON      = r'::'
t_EQUALS           = r'='
t_SEMI             = r';'

# Identifiers
t_ID               = r'[A-Za-z_]\w*'

# A regular expression rule with some action code
def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

# String literal
def t_STRING(t):
    r'\"([^\\\n]|(\\.))*?\"'
    t.value = str(t.value[1:-1].encode().decode("unicode_escape"))
    return t

def t_error(t):
    raise SyntaxError("Illegal character {0!r}".format(t.value[0]),
                      loc(t).to_syntax_error_tuple())


lexer = ply.lex.lex(optimize=1, lextab=None)
lexer.ignore_newline_stack = [0]

if __name__ == "__main__":
    ply.lex.runmain(lexer)

