"""
Glue code between nsloaders and Mybuild bindings for py/my DSL files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-08-07"


from _compat import *

from nsloader import myfile
from nsloader import pyfile

from mybuild.binding import mydsl
from mybuild.binding import pydsl


class MyDslLoader(myfile.MyFileLoader):

    FILENAME = 'Mybuild'

    @property
    def defaults(self):
        return dict(super(MyDslLoader, self).defaults,
                    module=mydsl.module,
                    option=mydsl.option)


class PyDslLoader(pyfile.PyFileLoader):

    FILENAME = 'Pybuild'

    @property
    def defaults(self):
        return dict(super(PyDslLoader, self).defaults,
                    module=pydsl.module,
                    option=pydsl.option)


