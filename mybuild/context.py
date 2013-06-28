"""
Types used on a per-build basis.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-09"

__all__ = ["Context"]


from collections import defaultdict
from collections import deque
from collections import MutableSet
from contextlib import contextmanager
from itertools import chain
from itertools import product
from operator import attrgetter

from core import *
from instance import Instance
from instance import InstanceError
from instance import InstanceNode
from pgraph import *
from util import NotifyingMixin
from util import pop_iter

from compat import *
import logs as log

# from mybuild.common.module import ModuleBuildOps
ModuleBuildOps = object

class Context(object):
    """docstring for Context"""

    def __init__(self):
        super(Context, self).__init__()
        self.modules = {}
        self._job_queue = deque()
        self._reent_locked = False

    def post(self, job_func):
        with self.reent_lock():  # to flush the queue on block exit
            self._job_queue.append(job_func)

    @contextmanager
    def reent_lock(self):
        was_locked = self._reent_locked
        self._reent_locked = True

        try:
            yield
        finally:
            if not was_locked:
                self._job_queue_flush()
            self._reent_locked = was_locked

    def _job_queue_flush(self):
        for job_func in pop_iter(self._job_queue, pop_meth='popleft'):
            job_func()

    def consider(self, module, option=None, value=Ellipsis):
        domain = self.domain_for(module)
        if option is not None:
            domain.consider_option(option, value)

    def domain_for(self, module, option=None):
        try:
            domain = self.modules[module]
        except KeyError:
            with self.reent_lock():
                domain = self.modules[module] = ModuleDomain(self, module)

        if option is not None:
            domain = domain.domain_for(option)

        return domain

    def create_pgraph(self):
        g = ContextPgraph()

        for domain in itervalues(self.modules):
            domain.init_pgraph(g)

        return g


class ContextPgraph(Pgraph):

    def __init__(self):
        super(ContextPgraph, self).__init__()

    def atom_for(self, module, option=None, value=Ellipsis):
        if option is None:
            return self.new_node(ModuleAtom, module)
        else:
            return self.new_node(OptionValueAtom, module, option, value)

    def pnode_for(self, mslice):
        # TODO should accept arbitrary expr as well.

        return self.new_node(And, *self._mslice_to_conjunction(mslice))

    def _mslice_to_conjunction(self, mslice):
        mslice = mslice._to_optuple()
        module = mslice._module

        option_atoms = [self.atom_for(module, option, value)
                        for option, value in mslice._iterpairs()]

        return option_atoms or [self.atom_for(module)]


@ContextPgraph.node_type
class ModuleAtom(Atom):

    def __init__(self, module):
        super(ModuleAtom, self).__init__()
        self.module = module

        self[False].level = 0  # first of all, try not to build a module

    def __repr__(self):
        return self.module._name


@ContextPgraph.node_type
class OptionValueAtom(Atom):

    def __init__(self, module, option, value):
        super(OptionValueAtom, self).__init__()

        self.module = module
        self.option = option
        self.value  = value

        is_default = (value == getattr(module._options, option).default)
        if is_default:
            # Whenever possible prefer default option value,
            # but do it after a stage of disabling modules.
            self[True].level = 1

    def __repr__(self):
        return '(%s.%s==%r)' % (self.module._name, self.option, self.value)


class DomainBase(object):
    """docstring for DomainBase"""

    def __init__(self, context):
        super(DomainBase, self).__init__()
        self.context = context


class ModuleDomain(DomainBase):
    """docstring for ModuleDomain"""

    def __init__(self, context, module):
        super(ModuleDomain, self).__init__(context)

        self.module = module

        self._instances = []
        self._options = module._options._mapwith(OptionDomain)

        self._instantiate_product(self._options)

    def _instantiate_product(self, iterables):
        make_optuple = self._options._make

        for new_tuple in product(*iterables):
            self._instances.append(InstanceDomain(self.context,
                                                  make_optuple(new_tuple)))

    def consider_option(self, option, value):
        domain_to_extend = getattr(self._options, option)
        if value in domain_to_extend:
            return

        log.debug('mybuild: extending %r with %r', domain_to_extend, value)
        domain_to_extend.add(value)

        self._instantiate_product(option_domain
            if option_domain is not domain_to_extend else (value,)
            for option_domain in self._options)

    def domain_for(self, option):
        return getattr(self._options, option)

    def init_pgraph(self, g):
        AllEqual(g, g.atom_for(self.module),
              *(option.create_pnode(g) for option in self._options))

        for instance in self._instances:
            instance.init_pgraph(g)


class NotifyingSet(MutableSet, NotifyingMixin):
    """Set with notification support."""

    def __init__(self, values=()):
        super(NotifyingSet, self).__init__()
        self._set = set()

        for value in values:
            self.add(value)

    def add(self, value):
        if value in self:
            return

        self._set.add(value)
        self._notify(value)

    def discard(self, value):
        if value not in self:
            return
        raise NotImplementedError

    def __iter__(self):
        return iter(self._set)
    def __len__(self):
        return len(self._set)
    def __contains__(self, value):
        return value in self._set

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, list(self))


class OptionDomain(NotifyingSet):
    """docstring for OptionDomain"""

    def __init__(self, option):
        super(OptionDomain, self).__init__()
        self.option = option
        self |= option._values

    def create_pnode(self, g):
        module = self.option._module
        option = self.option._name

        return AtMostOne(g, *(g.atom_for(module, option, value)
                              for value in self))


class InstanceDomain(DomainBase):

    module     = property(attrgetter('optuple._module'))
    _init_func = property(attrgetter('module._init_func'))

    def __init__(self, context, optuple):
        super(InstanceDomain, self).__init__(context)

        self.optuple = optuple

        self._instances = []
        self._node = root_node = InstanceNode()

        self.post_new(root_node)

    def post_new(self, node):
        instance = Instance(self, node)

        def init_instance():
            with log.debug("mybuild: new %s", instance):
                try:
                    self._init_func(instance, *self.optuple)
                except InstanceError as e:
                    log.debug("mybuild: unviable %s: %s", instance, e)
                else:
                    log.debug("mybuild: succeeded %s", instance)
                    self._instances.append(instance)

        self.context.post(init_instance)

    def init_pgraph(self, g):
        atoms = [InstanceAtom(g, instance) for instance in self._instances]

        for atom in atoms:
            atom.implies(atom.instance._node.create_decisions_pnode(g))

        optuple_instance = g.pnode_for(self.optuple)
        optuple_instance.equivalent(AtMostOne(g, *atoms))
        optuple_instance.implies(self._node.create_pnode(g))


@ContextPgraph.node_type
class InstanceAtom(Atom, ModuleBuildOps):

    def __init__(self, instance):
        super(InstanceAtom, self).__init__()
        self.instance = instance

    def __repr__(self):
        return repr(self.instance)

    def is_building(self, model):
        #return model[self]
        return True

    def get_sources(self):
        return getattr(self.instance, 'sources', [])

    def get_options(self):
        return []

    def qualified_name(self):
        return getattr(self.instance, 'qualified_name', '')

    def islib(self):
        return False

    def __getattr__(self, attr):
        return getattr(self.instance, attr)

if __name__ == '__main__':
    from mybuild import module, option
    from solver import solve

    log.zones = ['mybuild', 'dtree']
    log.verbose = True
    log.init_log()

    @module
    def conf(self):
        self.constrain(m1)
        self.constrain(iface)
        self.sources = 'test.c'

    @module
    def m1(self):
        if self._decide(m3):
            self.constrain(m2(foo=17))

    @module
    def m2(self, foo=42):
        self.provides(iface)

    @module
    def iface(self):
        pass

    @module
    def m3(self):
        pass

    context = Context()
    context.consider(conf)

    g = context.create_pgraph()

    solution = solve(g, {g.atom_for(conf):True})

    for pnode, value in iteritems(solution):
        if isinstance(pnode, InstanceAtom):
            print '>>>', value, pnode
            srcs = getattr(pnode.instance, 'sources', '')
            # print srcs

