"""
Location tracking needed for rich error reporting.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-29"


from util import cached_property
from util.compat import *


class Fileinfo(object):
    """Provides data necessary for lines and column lookup."""

    @cached_property
    def line_table(self):
        """Just a list of lines."""
        return self.source.splitlines(True)

    @cached_property
    def offset_table(self):
        """A table of line offsets indexed by line numbers.

        Has an extra element at the end, so its len is one more that len of
        the line_table."""
        offset = 0
        table = [0]
        for line_len in map(len, self.line_table):
            offset += line_len
            table.append(offset)
        return table

    def __init__(self, source, name=None):
        super(Fileinfo, self).__init__()
        self.source = source
        self.name = name

    def get_line(self, lineno):
        return self.line_table[lineno-1]

    def get_column(self, lineno, offset):
        line_start, line_end = self.offset_table[lineno-1:lineno+1]
        if not line_start <= offset < line_end:
            raise ValueError("position %d does not fall within the line %d" %
                             (offset, lineno))
        return offset - line_start + 1


class Location(object):
    """Encapsulates info about symbol location provided by PLY."""
    __slots__ = 'fileinfo', 'lineno', 'offset'

    @property
    def filename(self):
        return self.fileinfo.name

    @property
    def line(self):
        return self.fileinfo.get_line(self.lineno)

    @property
    def column(self):
        return self.fileinfo.get_column(self.lineno, self.offset)

    @property
    def syntax_error_tuple(self):
        """4-element tuple suitable to pass to a constructor of SyntaxError."""
        return (self.filename, self.lineno, self.column, self.line)

    def __init__(self, fileinfo, lineno, offset):
        super(Location, self).__init__()
        self.fileinfo = fileinfo
        self.lineno = lineno  # 1-base indexed
        self.offset = offset  # 0-based absolute char offset

    def __iter__(self):
        return iter(self.syntax_error_tuple)

