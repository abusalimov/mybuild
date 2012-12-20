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
from instance import InstanceNode
import pdag
from util import NotifyingMixin

import logs as log


class Context(object):
    """docstring for Context"""

    def __init__(self):
        super(Context, self).__init__()
        self._modules = {}
        self._job_queue = deque()
        self._reent_locked = False
        self._atom_cache = {}

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

    def atom_for(self, module, option=None, value=Ellipsis):
        cache = self._atom_cache
        cache_key = module, option, value

        try:
            return cache[cache_key]
        except KeyError:
            pass

        domain = self._modules[module]

        if option is not None:
            ret = domain.domain_for(option).atom_for(value)
        else:
            ret = domain.atom

        cache[cache_key] = ret

        return ret

    def create_pnode_from(self, mslice):
        # TODO should accept arbitrary expr as well.
        optuple = mslice._to_optuple()
        module = optuple._module

        return pdag.And(self.atom_for(module),
                        *(self.atom_for(module, option, value)
                          for option, value in optuple._iterpairs()))

    def create_pdag_with_constraint(self):
        constraint = pdag.And(*(module.create_constraint()
                                for module in self._modules.itervalues()))
        atoms = chain(*(module.iter_atoms()
                        for module in self._modules.itervalues()))
        return pdag.Pdag(*atoms), constraint


class DomainBase(object):
    """docstring for DomainBase"""

    context = property(attrgetter('_context'))

    def __init__(self, context):
        super(DomainBase, self).__init__()
        self._context = context


class ModuleDomain(DomainBase):
    """docstring for ModuleDomain"""

    module = property(attrgetter('_module'))
    atom = property(attrgetter('_atom'))

    def __init__(self, context, module):
        super(ModuleDomain, self).__init__(context)

        self._module = module
        self._atom = module._atom_type()

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

    def iter_atoms(self):
        return chain((self._atom,),
                     *(obj.iter_atoms()
                       for obj in chain(self._options, self._instances)))

    def create_constraint(self):
        # TODO don't like it
        pdag.AllEqualConstraint(self._atom,
            *(option.create_pnode() for option in self._options))
        return pdag.And(*(instance.create_constraint()
                          for instance in self._instances))


class NotifyingSet(MutableSet, NotifyingMixin):
    """Set with notification support. Backed by a dictionary."""

    def __init__(self, values):
        super(NotifyingSet, self).__init__()
        self._dict = {}

        self |= values

    def _create_value_for(self, key):
        pass

    def add(self, value):
        if value in self:
            return
        self._dict[value] = self._create_value_for(value)

        self._notify(value)

    def discard(self, value):
        if value not in self:
            return
        raise NotImplementedError

    def __iter__(self):
        return iter(self._dict)
    def __len__(self):
        return len(self._dict)
    def __contains__(self, value):
        return value in self._dict

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self._dict.keys())


class OptionDomain(NotifyingSet):
    """docstring for OptionDomain"""

    def __init__(self, option):
        self._option = option
        super(OptionDomain, self).__init__(option._values)

    def atom_for(self, value):
        if value not in self:
            raise ValueError
        return self._dict[value]

    def _create_value_for(self, value):
        return self._option._atom_type(value)

    def iter_atoms(self):
        return self._dict.itervalues()

    def create_pnode(self):
        return pdag.AtMostOneConstraint(*self.iter_atoms())


class InstanceDomain(DomainBase):

    optuple = property(attrgetter('_optuple'))
    module  = property(attrgetter('_module'))

    _init_fxn = property(attrgetter('_optuple._module._init_fxn'))

    def __init__(self, context, optuple):
        super(InstanceDomain, self).__init__(context)

        self._optuple = optuple

        self._atoms = []
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
                    self._atoms.append(InstanceAtom(instance))

        self._context.post(new)

    def iter_atoms(self):
        return iter(self._atoms)

    def create_constraint(self):
        context = self._context

        constraint = pdag.AllEqualConstraint(
            context.create_pnode_from(self._optuple),
            pdag.AtMostOneConstraint(*self._atoms))

        return pdag.And(pdag.Implies(constraint,
                                     self._node.create_pnode(context)),
            *(pdag.Implies(atom,
                atom.instance._node.create_pnode_for_decisions(context))
              for atom in self._atoms))


class InstanceAtom(pdag.Atom):
    __slots__ = '_instance'

    instance = property(attrgetter('_instance'))

    def __init__(self, instance):
        super(InstanceAtom, self).__init__()
        self._instance = instance

    def __repr__(self):
        return repr(self._instance)


if __name__ == '__main__':
    from mybuild import module, option

    log.zones = ['mybuild', 'pdag']
    log.verbose = True
    log.init_log()

    @module
    def conf(self):
        self.constrain(m1)

    @module
    def m1(self):
        if self._decide(m3):
            self.constrain(m2(foo=17))

    @module
    def m2(self, foo=42):
        self.constrain(m3)

    @module
    def m3(self):
        pass

    context = Context()
    context.consider(conf)

    conf_atom = context.atom_for(conf)
    pdag, constraint = context.create_pdag_with_constraint()
    dtree = Dtree(pdag)
    # solution = dtree.solve({constraint:True, conf_atom:True,
    #                        context.atom_for(m3):False})

    from collections import OrderedDict
    solution = dtree.solve(OrderedDict([(constraint, True),
                                        (conf_atom, True),
                                        (context.atom_for(m3), False)]))

    # from pprint import pprint
    # pprint(solution)
    for pnode, value in solution.iteritems():
        if isinstance(pnode, InstanceAtom):
            print value, pnode

