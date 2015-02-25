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
                    MYBUILD_VERSION=mybuild.__version__)


class WafBasedTool(mybuild.core.Tool):
    waf_tools = []

    def options(self, module, ctx):
        ctx.load(self.waf_tools)
    def configure(self, module, ctx):
        ctx.load(self.waf_tools)


class CcTool(WafBasedTool):
    waf_tools = ['compiler_c']

    def __init__(self):
        super(CcTool, self).__init__()
        self.build_kwargs = {}

    def create_namespaces(self, module):
        return dict(cc=Namespace(defines=Namespace()))

    def define(self, key, val):
        assert('defines' in self.build_kwargs)
        format_str = '{0}=\"{1}\"' if isinstance(val, str) else '{0}={1}'
        self.build_kwargs['defines'].append(format_str.format(key, val))

    def build(self, module, ctx):
        self.build_kwargs['use'] = [m._name for m in module.depends]
        self.build_kwargs['source'] = module.files
        self.build_kwargs['target'] = module._name
        self.build_kwargs['defines'] = []

        for k, v in iteritems(module.cc.defines.__dict__):
            self.define(k, v)


class CcObjTool(CcTool):
    def build(self, module, ctx):
        super(CcObjTool, self).build(module, ctx)
        ctx.objects(**self.build_kwargs)


class CcAppTool(CcTool):
    def build(self, module, ctx):
        super(CcAppTool, self).build(module, ctx)
        ctx.program(**self.build_kwargs)


class CcLibTool(CcTool):
    def build(self, module, ctx):
        super(CcLibTool, self).build(module, ctx)
        if module.isstatic:
            ctx.stlib(**self.build_kwargs)
        else:
            ctx.shlib(**self.build_kwargs)


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

