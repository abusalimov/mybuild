"""
Mybuild high-level types.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2015-05-21"

__all__ = [
    "Module",
    "InterfaceModule",
    "CompoundModule",
    "Project",
    "Tool",
    "Optype",
    "MybuildError",
]


from _compat import *


from mybuild.core import ModuleBase
from mybuild.core import Optype
from mybuild.core import MybuildError

from util.prop import cached_property
from util.prop import cached_class_property

class Module(ModuleBase):
    """Provides a data necessary for Context."""

    @cached_property
    def tools(self):
        return []

    @cached_property
    def includes(self):
        return []

    # TODO: remove it as redundant
    @cached_property
    def depends(self):
        return []

    @cached_property
    def build_depends(self):
        return []

    @cached_property
    def runtime_depends(self):
        return []

    @cached_class_property
    def provides(cls):
        return [cls]

    @cached_class_property
    def default_provider(cls):
        return None

    @cached_property
    def files(self):
        return []

    @cached_property
    def _builders(self):
        ret = []
        for tool in self.tools:
            for name, builder_type in iteritems(tool.builder_map):
                builder = builder_type(self)
                ret.append(builder)
                try:
                    ns = getattr(self, name)
                except AttributeError:
                    continue
                else:
                    builder.setup(ns)
        return ret

    def __init__(self, optuple, container=None):
        super(Module, self).__init__(optuple, container)

        # self._constraints = []  # [(optuple, condition)]

        # self.tools = [tool() for tool in self.tools]
        # for tool in self.tools:
        #     for attr, value in iteritems(tool.create_namespaces(self)):
        #         if not hasattr(self, attr):
        #             setattr(self, attr, value)

    def build(self, stage='build'):
        for builder in self._builders:
            builder.build(stage)

    def __setattr__(self, name, value):
        try:
            tool = self._tool_map[name]
        except KeyError:
            pass
        else:
            value = tool.from_dict(value.__dict__)

        super(Module, self).__setattr__(name, value)

    def _post_init(self):
        # TODO: remove it as redundant
        for dep in self.depends:
            self._add_constraint(dep)

        for dep in self.build_depends:
            self._add_constraint(dep)

        for interface in self.provides:
            self._discover(interface)

        if self.default_provider is not None:
            self._discover(self.default_provider)

    def _add_constraint(self, mslice, condition=True):
        self._constraints.append((mslice(), condition))

    def _discover(self, mslice):
        self._add_constraint(mslice, condition=False)

    _constrain = _add_constraint


class InterfaceModule(Module):
    provides = []
    default_provider = None


class Project(Module):
    pass


class Tool(object):
    """docstring for Tool"""

    builder_map = {}

    @classmethod
    def from_dict(cls, dict_):
        instance = cls.__new__(cls)
        instance.__dict__ = dict_
        return instance

    def create_namespaces(self, instance):
        return {}

    def initialize_module(self, instance):
        pass


class Builder(object):
    """docstring for Builder"""

    def __init__(self, module):
        super(Builder, self).__init__()
        self.module = module

    def setup(self, ns):
        pass

