"""
Glue code between nsloaders and Mybuild bindings for py/my DSL files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-08-07"


from _compat import *

import re

from nsloader import myfile
from nsloader import pyfile

import mybuild
from mybuild.binding import pydsl

from util.operator import attr
from util.namespace import Namespace
from util.prop import cached_property
from util.misc import stringify


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
    def __init__(self):
        super(WafBasedTool, self).__init__()
        self.waf_tools = []

    def options(self, module, ctx):
        ctx.load(self.waf_tools)

    def configure(self, module, ctx):
        ctx.load(self.waf_tools)

def interpolate_string(string, env):
    pattern = re.compile('.*\${(\w+)}.*')
    match = re.search(pattern, string)
    while match:
        res = match.group(1)
        string = string.replace('${' + res + '}', env[res])
        match = re.search(pattern, string)
    return string

class CcTool(WafBasedTool):
    def __init__(self):
        super(CcTool, self).__init__()
        self.waf_tools += ['gcc', 'c', 'ar']
        self.build_kwargs = {}

    def create_namespaces(self, module):
        return dict(cc=Namespace(defines=Namespace()))

    def define(self, key, val):
        assert('defines' in self.build_kwargs)
        if isinstance(val, str):
            val = stringify(val)
        self.build_kwargs['defines'].append('{0}={1}'.format(key, val))

    def build(self, module, ctx):
        sources = []
        objects = []

        for fname in module.files:
            if re.match('.*\.o', fname):
                objects.append(fname)
            elif re.match('.*\.[cS]', fname):
                sources.append(fname)

        includes = ctx.env.includes + module.includes
        includes = [interpolate_string(s, ctx.env) for s in includes]

        self.build_kwargs['source'] = sources
        self.build_kwargs['target'] = module._name
        self.build_kwargs['includes'] = includes

        mod_name = module._fullname.replace('.', '__')
        self.build_kwargs['defines'] = ['__EMBUILD_MOD__=' + mod_name]

        config_header = 'config/' + module._fullname.replace('.', '/') + '.h'
        self.build_kwargs['cflags'] = ['-include', config_header]

        for k, v in iteritems(module.cc.defines.__dict__):
            self.define(k, v)


class CcObjTool(CcTool):
    def build(self, module, ctx):
        super(CcObjTool, self).build(module, ctx)
        ctx(features='c', **self.build_kwargs)


class CcAppTool(CcTool):
    def build(self, module, ctx):
        super(CcAppTool, self).build(module, ctx)

        use = [instance._name for instance in ctx.instance_map \
               if instance._name != module._name]

        self.build_kwargs['use'] = use

        ctx(features='c cprogram', **self.build_kwargs)


class CcLibTool(CcTool):
    def build(self, module, ctx):
        super(CcLibTool, self).build(module, ctx)
        if module.isstatic:
            ctx(features='c cstlib', **self.build_kwargs)
        else:
            ctx(features='c cshlib', **self.build_kwargs)


class GenHeadersTool(WafBasedTool):
    def get_headers(self, module):
        headers = []

        project_relative_path = '/'.join(module.__module__.split('.')[1:-1])
        preproc_relative_path = '../../src/{0}/'.format(project_relative_path)

        for fname in module.files:
            if re.match('.*\.h', fname):
                headers.append(preproc_relative_path + fname)
        return headers

    def get_option_string(self, mod_name, opt_name, value):
        if isinstance(value, str):
            opt_type = 'STRING'
        elif isinstance(value, bool):
            opt_type = 'BOOLEAN'
            value = 1 if value else 0
        elif isinstance(value, int):
            opt_type = 'NUMBER'
        else:
            raise Exception('Option with type {0} is not supported' \
                            .format(type(value)))

        fmt = 'OPTION_{TYPE}_{MOD}__{NAME} {VALUE}'

        return fmt.format(TYPE=opt_type, MOD=mod_name, NAME=opt_name,
                          VALUE=value)

    def get_options(self, module):
        options = []

        options_dict = module._ModuleBase__optuple.__dict__
        for opt_name, opt_val in iteritems(options_dict):
            mod_name = module._fullname.replace('.', '__')
            options.append(self.get_option_string(mod_name, opt_name, opt_val))

        return options

    def build(self, module, ctx):
        headers = self.get_headers(module)
        options = self.get_options(module)

        # TODO: Generate headers for several aliases
        alias = module.provides[1] if len(module.provides) > 1 else module
        alias_name = alias._fullname
        module_name = module._fullname

        module_fmt = 'module/{0}.h'
        config_fmt = 'config/{0}.h'

        module_output = module_fmt.format(module_name.replace('.', '/'))
        config_output = config_fmt.format(module_name.replace('.', '/'))

        module_output_alias = module_fmt.format(alias_name.replace('.', '/'))
        config_output_alias = config_fmt.format(alias_name.replace('.', '/'))

        module_guard = module_name.replace('.', '_').upper()
        alias_guard = alias_name.replace('.', '_').upper()

        ctx(features='module_header', name=module_name,
            includes=headers + [config_output],
            output_header=module_output,
            guard=module_guard)

        ctx(features='module_header', name=module_name,
            options=options,
            output_header=config_output,
            guard='CONFIG_' + module_guard)

        if alias_name != module_name:
            ctx(features='module_header', name=module_name,
                includes=[module_output],
                output_header=module_output_alias,
                guard=alias_guard)

            ctx(features='module_header', name=module_name,
                includes=[config_output],
                output_header=config_output_alias,
                guard='CONFIG_' + alias_guard)


tool = Namespace(cc=CcObjTool, cc_app=CcAppTool, cc_lib=CcLibTool,
                 gen_headers=GenHeadersTool)


class MyDslLoader(LoaderMixin, myfile.MyFileLoader):
    FILENAME = 'Config'

    class CcModule(mybuild.core.Module):
        tools = [CcObjTool, GenHeadersTool]

    class ApplicationCcModule(mybuild.core.Module):
        tools = [CcAppTool, GenHeadersTool]

    class LibCcModule(mybuild.core.Module):
        tools = [CcLibTool, GenHeadersTool]

        @cached_property
        def isstatic(self):
            return True


    dsl = Namespace()
    dsl.module       = CcModule._meta_for_base(option_types=[])
    dsl.application  = ApplicationCcModule._meta_for_base(option_types=[])
    dsl.library      = LibCcModule._meta_for_base(option_types=[])
    dsl.option       = mybuild.core.Optype
    dsl.project      = None


class PyDslLoader(LoaderMixin, pyfile.PyFileLoader):
    FILENAME = 'Pybuild'
    dsl = pydsl

