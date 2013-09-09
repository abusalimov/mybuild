"""
Glue code between nsloaders and Mybuild bindings for py/my DSL files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-08-07"


from _compat import *

from nsloader import myfile
from nsloader import pyfile

import mybuild
from mybuild.binding import mydsl
from mybuild.binding import pydsl

from util.operator import attr
from util.prop import cumulative_mapping_property


class LoaderMixin(object):

    dsl = None

    @property
    def defaults(self):
        return dict(super(LoaderMixin, self).defaults,
                    module  = self.dsl.module,
                    project = self.dsl.project,
                    option  = self.dsl.option,
                    tool=tool,
                    MYBUILD_VERSION=mybuild.__version__)


class MyDslLoader(LoaderMixin, myfile.MyFileLoader):
    FILENAME = 'Mybuild'
    dsl = mydsl


class PyDslLoader(LoaderMixin, pyfile.PyFileLoader):
    FILENAME = 'Pybuild'
    dsl = pydsl



class NsObject(object):
    """docstring for NsObject"""

    def __init__(self, dict_={}, **kwargs):
        super(NsObject, self).__init__()
        self.__dict__.update(dict_, **kwargs)

class RoNsObject(NsObject):
    """docstring for RoNsObject"""

    def __setattr__(self, attr, value):
        raise AttributeError
    def __delattr__(self, attr):
        raise AttributeError


class WafBasedTool(mybuild.core.Tool):
    waf_tools = []

    def options(self, module, ctx):
        ctx.load(self.waf_tools)
    def configure(self, module, ctx):
        ctx.load(self.waf_tools)


class CcNs(NsObject):
    defines = cumulative_mapping_property(attr.__defines)

class CcTool(WafBasedTool):
    waf_tools = ['compiler_c']

    def create_namespaces(self, module):
        return dict(cc=CcNs())

    def build(self, module, ctx):
        for name, value in iteritems(module.cc.defines):
            ctx.define(name, value)
        ctx.program(source=module.files, target=module._name)

tool = NsObject(cc=CcTool())

