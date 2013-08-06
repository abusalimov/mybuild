"""
Types used on a per-build basis.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-09"

__all__ = ["Context"]


from collections import namedtuple
from collections import defaultdict
from itertools import product
from operator import attrgetter

from .core import *
from .instance import InstanceError
from .instance import InstanceNode
from .pgraph import *
from util import NotifyingMixin
from util import pop_iter
from util import no_reent

from util.compat import *

import logs as log


class Context(object):
    """docstring for Context"""

    def __init__(self, instance_type=object):
        super(Context, self).__init__()
        self.instance_type = instance_type

        self._instances = dict()  # {optuple: instance}
        self._mdata     = dict()  # {module: mdata}

        self._constraints = defaultdict(set)  # {optuple: optuples...}

    @no_reent
    def _instantiate(self, mdata, optuple, origin=None):
        log.debug("mybuild: new %s (posted by %s)", optuple, origin)
        try:
            instance = mdata.ctxtype._instantiate(optuple)
        except InstanceError as e:
            log.debug("mybuild:     %s unviable: %s", optuple, e)
            instance = None

        assert optuple not in self._instances
        self._instances[optuple] = instance

    def _instantiate_product(self, mdata, iterables_optuple, origin=None):
        for optuple in map(iterables_optuple._make,
                           product(*iterables_optuple)):
            self._instantiate(mdata, optuple, origin)

    def consider(self, mslice, origin=None):
        optuple = mslice()
        mdata = self.mdata_for(optuple._module)

        for value, domain_to_extend in optuple._zipwith(mdata.domain):
            if value in domain_to_extend:
                continue

            domain_to_extend.add(value)

            self._instantiate_product(mdata, optuple._make(option_domain
                    if option_domain is not domain_to_extend else (value,)
                    for option_domain in mdata.domain), origin)

    def constrain(self, mslice, origin=None):
        optuple = mslice()
        self.consider(optuple, origin)

        self._constraints[origin].add(optuple)


    def mdata_for(self, module):
        try:
            mdata = self._mdata[module]
        except KeyError:
            mdata = self._mdata[module] = ModuleData(self, module)
            self._instantiate_product(mdata, mdata.domain)

        return mdata

    def create_pgraph(self):
        g = ContextPgraph(self)

        for mdata in itervalues(self._mdata):
            mdata.init_pgraph(g)

        # for optuple, instance in iteritems(self._instances):
        #     instance.init_pgraph(g)

        # for optuple, constraints in iteritems(self._constraints):
        #     instance = self._instances[optuple]
        #     for constraint in constraints:
        #         Implies(g, , g.pnode_for(constraint))

        return g


class ModuleData(namedtuple('ModuleData', 'ctxtype, domain')):
    __slots__ = ()

    context = property(attrgetter('ctxtype._context'))
    module  = property(attrgetter('ctxtype._module'))

    def __new__(cls, context, module):
        return super(ModuleData, cls).__new__(cls,
                ctxtype=cls._create_ctxtype(context, module),
                domain=cls._create_domain(module))

    @classmethod
    def _create_ctxtype(cls, context, module):
        # Mix context specific instance_type into a module class.
        type_dict = dict(__module__ = module.__module__,
                         __doc__    = module.__doc__,
                         _module    = module,
                         _context   = context)
        bases = (module, context.instance_type)

        return type(module.__name__, bases, type_dict)

    @classmethod
    def _create_domain(cls, module):
        return module._opmake(set(optype._values)
                              for optype in module._optypes)

    def init_pgraph(self, g):
        module = self.module
        module_atom = ModuleAtom(g, module)

        for option, values in self.domain._iterpairs():
            option_atoms = (g.atom_for(module, option, value) for value in values)
            option_node = AtMostOne(g, option_atoms,
                    why_one_operand_zero_implies_others_identity=
                        why_option_can_have_at_most_one_value,
                    why_identity_implies_all_operands_identity=
                        why_disabled_option_cannot_have_a_value,
                    why_all_operands_identity_implies_identity=
                        why_option_with_no_value_must_be_disabled)

            module_atom.equivalent(option_node,
                    why_becauseof=why_option_implies_module,
                    why_therefore=why_module_implies_option)


class ContextPgraph(Pgraph):

    def __init__(self, context):
        super(ContextPgraph, self).__init__()
        self.context = context

    def atom_for(self, module, option=None, value=Ellipsis):
        if option is None:
            return self.new_node(ModuleAtom, module)
        else:
            return self.new_node(OptionValueAtom, module, option, value)

    def pnode_for(self, mslice):
        # TODO should accept arbitrary expr as well.
        optuple = mslice()
        if optuple._complete:
            self.context

        return self.new_node(And, *self._mslice_to_conjunction(mslice))

    def _mslice_to_conjunction(self, mslice):
        mslice = mslice()
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
        return repr(self.module())


@ContextPgraph.node_type
class OptionValueAtom(Atom):

    def __init__(self, module, option, value):
        super(OptionValueAtom, self).__init__()
        self.module = module
        self.option = option
        self.value  = value

        is_default = (value == module._optype(option).default)
        if is_default:
            # Whenever possible prefer default option value,
            # but do it after a stage of disabling modules.
            self[True].level = 1

    def __repr__(self):
        return repr(self.module(**{self.option: self.value}))


@ContextPgraph.node_type
class InstanceAtom(Atom):

    def __init__(self, instance):
        super(InstanceAtom, self).__init__()
        self.instance = instance

    def __repr__(self):
        return repr(self.instance)


def why_option_can_have_at_most_one_value(outcome, *causes):
    return 'option can have at most one value: %s: %s' % (outcome, causes)
def why_disabled_option_cannot_have_a_value(outcome, *causes):
    return 'disabled option cannot have a value: %s: %s' % (outcome, causes)
def why_option_with_no_value_must_be_disabled(outcome, *causes):
    return 'option with no value must be disabled: %s: %s' % (outcome, causes)
def why_option_implies_module(outcome, *causes):
    return 'option implies module: %s: %s' % (outcome, causes)
def why_module_implies_option(outcome, *causes):
    return 'module implies option: %s: %s' % (outcome, causes)


if __name__ == '__main__':
    from mybuild.dsl.pyfile import module, option
    from solver import solve

    log.zones = ['mybuild', 'dtree']
    log.verbose = True
    log.init_log()

    @module
    def conf(self):
        self._constrain(m1)
        self._constrain(m3)
        self.sources = 'test.c'

    @module
    def m1(self):
        self._constrain(m2(foo=17))

    @module
    def m2(self, foo=42):
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

