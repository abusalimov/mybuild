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
from dtree import Dtree
from instance import Instance
from instance import InstanceError
from instance import InstanceNode
from pdag import *
from util import NotifyingMixin

import logs as log

from mybuild.common.module import ModuleBuildOps

class Context(object):
    """docstring for Context"""

    def __init__(self):
        super(Context, self).__init__()
        self._modules = {}
        self._job_queue = deque()
        self._reent_locked = False

    def post(self, fxn):
        with self.reent_lock(): # to flush the queue on block exit
            self._job_queue.append(fxn)

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
        queue = self._job_queue

        while queue:
            fxn = queue.popleft()
            fxn()

    def consider(self, module, option=None, value=Ellipsis):
        domain = self.domain_for(module)
        if option is not None:
            domain.consider_option(option, value)

    def domain_for(self, module, option=None):
        try:
            domain = self._modules[module]
        except KeyError:
            with self.reent_lock():
                domain = self._modules[module] = ModuleDomain(self, module)

        if option is not None:
            domain = domain.domain_for(option)

        return domain

    def create_pdag(self):
        g = ContextPdag()

        for module in self._modules.itervalues():
            module.init_pdag(g)

        return g


class ContextPdag(Pdag):

    def __init__(self):
        super(ContextPdag, self).__init__()

    def atom_for(self, module, option=None, value=Ellipsis):
        if option is None:
            return self.new(ModuleAtom, module)
        else:
            return self.new(OptionValueAtom, module, option, value)

    def pnode_for(self, mslice):
        # TODO should accept arbitrary expr as well.

        return self.new(And, *self._mslice_to_conjunction(mslice))

    def _mslice_to_conjunction(self, mslice):
        mslice = mslice._to_optuple()
        module = mslice._module

        option_atoms = [self.atom_for(module, option, value)
                        for option, value in mslice._iterpairs()]

        return option_atoms or [self.atom_for(module)]


@ContextPdag.node_type
class ModuleAtom(Atom):
    __slots__ = '_module'

    def __init__(self, module):
        super(ModuleAtom, self).__init__()
        self._module = module

    def __repr__(self):
        return self._module._name


@ContextPdag.node_type
class OptionValueAtom(Atom):
    __slots__ = '_module', '_option', '_value'

    def __init__(self, module, option, value):
        super(OptionValueAtom, self).__init__()
        self._module = module
        self._option = option
        self._value  = value

    def __repr__(self):
        return '(%s.%s==%r)' % (self._module._name, self._option, self._value)


class DomainBase(object):
    """docstring for DomainBase"""

    context = property(attrgetter('_context'))

    def __init__(self, context):
        super(DomainBase, self).__init__()
        self._context = context


class ModuleDomain(DomainBase):
    """docstring for ModuleDomain"""

    module = property(attrgetter('_module'))

    def __init__(self, context, module):
        super(ModuleDomain, self).__init__(context)

        self._module = module

        self._instances = []
        self._options = module._options._make(OptionDomain(option)
                                              for option in module._options)

        self._instantiate_product(self._options)

    def _instantiate_product(self, iterables):
        make_optuple = self._options._make
        instances = self._instances

        for new_tuple in product(*iterables):
            new_optuple = make_optuple(new_tuple)

            instances.append(InstanceDomain(self._context, new_optuple))

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

    def init_pdag(self, g):
        g.new(AllEqualConstraint, g.atom_for(self._module),
              *(option.create_pnode(g) for option in self._options))

        for instance in self._instances:
            instance.init_pdag(g)


class NotifyingSet(MutableSet, NotifyingMixin):
    """Set with notification support."""

    def __init__(self, values):
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
        self._option = option
        super(OptionDomain, self).__init__(option._values)

    def create_pnode(self, g):
        module = self._option._module
        option = self._option._name

        return g.new(AtMostOneConstraint,
                     *(g.atom_for(module, option, value) for value in self))


class InstanceDomain(DomainBase):

    optuple = property(attrgetter('_optuple'))
    module  = property(attrgetter('_module'))

    _init_fxn = property(attrgetter('_optuple._module._init_fxn'))

    def __init__(self, context, optuple):
        super(InstanceDomain, self).__init__(context)

        self._optuple = optuple

        self._instances = []
        self._node = root_node = InstanceNode()

        self.post_new(root_node)

    def post_new(self, node):
        instance = Instance(self, node)

        def new():
            with log.debug("mybuild: new %s", instance):
                try:
                    self._init_fxn(instance, *self._optuple)
                except InstanceError as e:
                    log.debug("mybuild: unviable %s: %s", instance, e)
                else:
                    log.debug("mybuild: succeeded %s", instance)
                    self._instances.append(instance)

        self._context.post(new)

    def init_pdag(self, g):
        atoms = [g.new(InstanceAtom, instance) for instance in self._instances]
        at_most_one_instance = g.new(AtMostOneConstraint, *atoms)

        optuple_instance = g.new(AllEqualConstraint,
            g.pnode_for(self._optuple), at_most_one_instance)

        instance_decisions = [g.new(Implies, atom,
            atom.instance._node.create_decisions_pnode(g)) for atom in atoms]

        g.new(TrueConstraint, g.new(AllEqualConstraint,
            g.new(Implies, optuple_instance, self._node.create_pnode(g)),
            *instance_decisions))


@ContextPdag.node_type
class InstanceAtom(Atom, ModuleBuildOps):
    __slots__ = '_instance'

    instance = property(attrgetter('_instance'))

    def __init__(self, instance):
        super(InstanceAtom, self).__init__()
        self._instance = instance

    def __repr__(self):
        return repr(self._instance)

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
    from mybuild.mybuild import module, option

    log.zones = ['mybuild', 'pdag']
    log.verbose = True
    log.init_log()

    @module
    def conf(self):
        self.constrain(m1)
        self.constrain(iface)
        self.sources = 'test.c'

    @module
    def m1(self):
        self.constrain(m2(foo=17))

    @module
    def m2(self, foo=42):
        self.provides(iface)

    @module
    def iface(self):
        pass

    context = Context()
    context.consider(conf)

    g = context.create_pdag()

    dtree = Dtree(g)
    solution = dtree.solve({g.atom_for(conf):True})

    for pnode, value in solution.iteritems():
        if isinstance(pnode, InstanceAtom):
            print value, pnode
            srcs = getattr(pnode.instance, 'sources', '')
            print srcs

