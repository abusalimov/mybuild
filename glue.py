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
from util.namespace import *


class LoaderMixin(object):

    dsl = None

    @property
    def defaults(self):
        return dict(super(LoaderMixin, self).defaults,
                    module  = self.dsl.module,
                    project = self.dsl.project,
                    option  = self.dsl.option,
                    tool    = tool,
                    ns      = Namespace,
                    MYBUILD_VERSION=mybuild.__version__)


class MyDslLoader(LoaderMixin, myfile.MyFileLoader):
    FILENAME = 'Mybuild'
    dsl = mydsl


class PyDslLoader(LoaderMixin, pyfile.PyFileLoader):
    FILENAME = 'Pybuild'
    dsl = pydsl

class WafBasedTool(mybuild.core.Tool):
    waf_tools = []

    def options(self, module, ctx):
        ctx.load(self.waf_tools)
    def configure(self, module, ctx):
        ctx.load(self.waf_tools)

class CcTool(WafBasedTool):
    waf_tools = ['compiler_c']

    def create_namespaces(self, module):
        return dict(cc=Namespace(defines={}))

    def build(self, module, ctx):
        for name in module.cc.defines:
            ctx.define(name, module.cc.defines[name])
        ctx.program(source=module.files, target=module._name)

tool = Namespace(cc=CcTool())

