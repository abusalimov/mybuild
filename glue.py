"""
Glue code between nsloaders and Mybuild bindings for py/my DSL files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-08-07"


from _compat import *

from nsloader import myfile
from nsloader import pyfile

import mybuild
from mybuild.binding import pydsl

from util.operator import attr
from util.namespace import Namespace


class LoaderMixin(object):

    dsl = None

    @property
    def defaults(self):
        return dict(super(LoaderMixin, self).defaults,
                    module       = self.dsl.module,
                    application  = self.dsl.application,
                    library      = self.dsl.library,
                    project      = self.dsl.project,
                    option       = self.dsl.option,
                    tool         = tool,
                    ns           = Namespace,
                    MYBUILD_VERSION=mybuild.__version__)


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
        self.use = []
        for name in module.cc.defines:
            ctx.define(name, module.cc.defines[name])

        for m in module.depends:
            self.use.append(ctx.instance_map[m]._name)


class CcObjTool(CcTool):
    def build(self, module, ctx):
        super(CcObjTool, self).build(module, ctx)
        ctx.objects(source=module.files, target=module._name, use=self.use)


class CcAppTool(CcTool):
    def build(self, module, ctx):
        super(CcAppTool, self).build(module, ctx)
        ctx.program(source=module.files, target=module._name, use=self.use)


class CcLibTool(CcTool):
    def build(self, module, ctx):
        super(CcLibTool, self).build(module, ctx)
        if module.isstatic:
            ctx.stlib(source=module.files, target=module._name, use=self.use)
        else:
            ctx.shlib(source=module.files, target=module._name, use=self.use)


tool = Namespace(cc=CcObjTool(), cc_app=CcAppTool(), cc_lib=CcLibTool())


class MyDslLoader(LoaderMixin, myfile.MyFileLoader):
    FILENAME = 'Mybuild'

    class CcModule(mybuild.core.Module):
        tools = [tool.cc]

    class ApplicationCcModule(mybuild.core.Module):
        tools = [tool.cc_app]

    class LibCcModule(mybuild.core.Module):
        tools = [tool.cc_lib]
        isstatic = True

    dsl = Namespace()
    dsl.module       = CcModule._meta_for_base(option_types=[])
    dsl.application  = ApplicationCcModule._meta_for_base(option_types=[])
    dsl.library      = LibCcModule._meta_for_base(option_types=[])
    dsl.option       = mybuild.core.Optype
    dsl.project      = None


class PyDslLoader(LoaderMixin, pyfile.PyFileLoader):
    FILENAME = 'Pybuild'
    dsl = pydsl

