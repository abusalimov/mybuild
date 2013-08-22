"""
Location tracking needed for rich error reporting.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-29"


from _compat import *

from util.operator import getter
from util.prop import cached_property


class Fileinfo(object):
    """Provides data necessary for lines and column lookup."""

    def __init__(self, source, name=None):
        super(Fileinfo, self).__init__()
        self.source = source
        self.name = name

        self.line_table   = lines   = source.splitlines(True)
        self.offset_table = offsets = [0]

        offset = 0
        for line_len in map(len, lines):
            offset += line_len
            offsets.append(offset)

    def get_line(self, lineno):
        return self.line_table[lineno-1]

    def get_column(self, lineno, offset):
        line_start, line_end = self.offset_table[lineno-1:lineno+1]
        if not line_start <= offset < line_end:
            raise ValueError("position {offset} does not fall "
                             "within the line {lineno}".format(**locals()))
        return offset - line_start + 1


class Location(object):
    """Encapsulates info about symbol location provided by PLY."""

    @cached_property
    def filename(self):
        return self.fileinfo.name

    @cached_property
    def line(self):
        return self.fileinfo.get_line(self.lineno)

    @cached_property
    def column(self):
        return self.fileinfo.get_column(self.lineno, self.offset)
    col_offset = property(getter.column)  # alias for ast.Node

    def __init__(self, fileinfo=None, lineno=None, offset=None):
        super(Location, self).__init__()

        if fileinfo is not None: self.fileinfo = fileinfo
        if lineno   is not None: self.lineno   = lineno  # 1-base indexed
        if offset   is not None: self.offset   = offset  # 0-based abs offset

    @classmethod
    def from_syntax_error(cls, syntax_error, fileinfo=None):
        new = cls(fileinfo)
        new.filename, new.lineno, new.column, new.line = syntax_error.args[1]
        return new

    @classmethod
    def from_ast_node(cls, ast_node, fileinfo=None):
        new = cls(fileinfo)
        new.lineno, new.column = ast_node.lineno, ast_node.col_offset
        return new

    def to_syntax_error_tuple(self):
        """4-element tuple suitable to pass to a constructor of SyntaxError."""
        return (self.filename, self.lineno, self.column, self.line)

    def to_ast_node_kwargs(self):
        """Keyword arguments dict suitable to initialize an ast.Node."""
        return dict(lineno=self.lineno, col_offset=self.column)

    def init_ast_node(self, ast_node):
        """Attaches location info to an ast.Node object."""
        for attr in 'lineno', 'col_offset':
            if attr in ast_node._attributes:
                setattr(ast_node, attr, getattr(self, attr))
        return ast_node

