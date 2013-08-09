"""
Glue code between nsloaders and Mybuild bindings for py/my DSL files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-08-07"


from nsloader import myfile
from nsloader import pyfile
from nsloader import yamlfile

from mybuild.binding import mydsl
from mybuild.binding import pydsl

from util.compat import *


class DslLoaderMixin(object):

    @classmethod
    def init_ctx(cls, ctx, initials=None):
        new_initials = dict(cls.default_initials())
        if initials is not None:
            new_initials.update(initials)

        return super(DslLoaderMixin, cls).init_ctx(ctx, new_initials)

    @classmethod
    def default_initials(cls):
        return {}


class MyDslLoader(DslLoaderMixin, myfile.MyFileLoader):

    MODULE = 'Mybuild'

    @classmethod
    def default_initials(cls):
        return {'module': mydsl.module,
                'option': mydsl.option}


class PyDslLoader(DslLoaderMixin, pyfile.PyFileLoader):

    MODULE = 'Pybuild'

    @classmethod
    def default_initials(cls):
        return {'module': pydsl.module,
                'option': pydsl.option}



class YamlDslLoader(DslLoaderMixin, yamlfile.YamlFileLoader):

    MODULE = 'MyYaml'

    @classmethod
    def default_initials(cls):

        def module(pymodule_name, dictionary):
            dictionary = dict(dictionary)

            def module_func(self):
                for key, value in dictionary:
                    setattr(self, key, value)
            module_func.__module__ = pymodule_name
            module_func.__name__ = dictionary.pop('id')

            return pydsl.module(module_func)

        return {'!module': module}

