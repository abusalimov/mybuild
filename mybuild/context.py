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
from functools import partial
from itertools import chain
from itertools import izip
from itertools import izip_longest
from itertools import product
from operator import attrgetter

from core import *
from instance import Instance
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

    def freeze(self):
        if hasattr(self, '_pdag'):
            raise RuntimeError("'freeze' must be called only once.")

        # def iter_atoms():
        #     for module_domain in self._module.itervalues():


        self._pdag = pdag.Pdag(*iter_atoms())

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

    def register(self, instance):
        self.domain_for(instance._module).register(instance)

    def domain_for(self, module, option=None):
        try:
            domain = self._modules[module]
        except KeyError:
            with self.reent_lock():
                domain = self._modules[module] = ModuleDomain(self, module)

        if option is not None:
            domain = domain.domain_for(option)

        return domain

    def atom_for(self, module, option=None, value=Ellipsis, negated=False):
        cache = self._atom_cache
        cache_key = module, option, value, negated

        try:
            return cache[cache_key]
        except KeyError:
            pass

        if negated:
            ret = pdag.Not(self.atom_for(module, option, value, negated=False))
        else:
            domain = self.domain_for(module, option)
            ret = domain.atom if option is None else domain.atom_for(value)

        cache[cache_key] = ret

        return ret

    def pnode_from(self, mslice):
        # TODO should accept arbitrary expr as well.
        pass


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

        self._instances = {} # { optuple : InstanceDomain }
        self._options = module._options._make(OptionDomain(option)
                                              for option in module._options)

        self._instantiate_product(self._options)

    def init_pnode(self):
        presence_pnode = pdag.EqGroup(self._atom,
            *(option_domain.pnode for option_domain in self._options))
        instances_pnode = pdag.And(
            *(instance.pnode
              for instance_set in self._instances.itervalues()
              for instance in instance_set))

    def _instantiate_product(self, iterables):
        make_optuple = self._options._make
        instances = self._instances

        for new_tuple in product(*iterables):
            new_optuple = make_optuple(new_tuple)

            assert new_optuple not in instances
            instances[new_optuple] = InstanceDomain(self._context, new_optuple)

    def consider_option(self, option, value):
        domain_to_extend = getattr(self._options, option)
        if value in domain_to_extend:
            return

        log.debug('mybuild: extending %r with %r', domain_to_extend, value)
        domain_to_extend.add(value)

        self._instantiate_product(
            option_domain if option_domain is not domain_to_extend else (value,)
            for option_domain in self._options)

    def domain_for(self, option):
        return getattr(self._options, option)


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

    def __str__(self):
        return '<%s: %s>' % (type(self).__name__, self._dict.keys())


class OptionDomain(NotifyingSet):
    """docstring for OptionDomain"""

    def __init__(self, option):
        self._option = option
        self.pnode = pdag.AtMostOne()

        super(OptionDomain, self).__init__(option._values)

    def atom_for(self, value):
        if value not in self:
            self.add(value)
        return self._dict[value]

    def _create_value_for(self, value):
        atom = self._option._atom_type(value)
        return self.pnode._new_operand(atom)


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
            with log.debug("mybuild: new %r", self):
                try:
                    self._init_fxn(*optuple)
                except InstanceError as e:
                    log.debug("mybuild: unviable %r: %s", self, e)
                else:
                    log.debug("mybuild: succeeded %r", self)
                    self._instances.append(instance)

        self._context.post(new)

    def create_pnode(self):
        return self._node.create_pnode(self._context)


if __name__ == '__main__':
    from mybuild import module, option

    log.zones = {'mybuild'}
    log.verbose = True
    log.init_log()

    @module
    def conf(self):
        self.constrain(m1)

    @module
    def m1(self):
        pass

    # build(conf)

