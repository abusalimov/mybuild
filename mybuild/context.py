"""
Types used on a per-build basis.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-09"

__all__ = [
    "Context",
    "resolve",
]


from _compat import *

from collections import namedtuple
from collections import defaultdict
from functools import partial
from itertools import product
from itertools import starmap
from operator import attrgetter

from mybuild.core import *
from mybuild.pgraph import *
from mybuild.solver import solve

from util.itertools import pop_iter
from util.misc import NotifyingMixin
from util.misc import no_reent

import logging
logger = logging.getLogger(__name__)


class Context(object):
    """docstring for Context"""

    def __init__(self, module_mixin=object):
        super(Context, self).__init__()
        self.module_mixin = module_mixin

        self._mdata = dict()  # {module: mdata}

        self._instances_alive = dict()   # {optuple: instance}
        self._instance_errors = dict()   # {optuple: error}

        self._constraints = defaultdict(set)  # {instance: optuples...}

    @no_reent
    def _instantiate(self, mdata, optuple, origin=None):
        logger.debug("new %s (posted by %s)", optuple, origin)
        try:
            instance = mdata.ctxtype._instantiate(optuple)
        except InstanceError as error:
            logger.debug("    %s inviable: %s", optuple, error)
            self._instance_errors[optuple] = error
        else:
            self._instances_alive[optuple] = instance

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

        for optuple, instance in iteritems(self._instances_alive):
            g.node_for(optuple).instance = instance

        for optuple, error in iteritems(self._instance_errors):
            optuple_node = g.node_for(optuple)
            optuple_node.error = error
            g.new_const(False, optuple_node,
                        why=why_inviable_instance_is_disabled)

        for origin, constraints in iteritems(self._constraints):
            if origin is not None:
                origin_node = g.node_for(origin._optuple)
            else:
                origin_node = g.new_const(True)

            origin_node.implies_all(map(g.node_for, constraints),
                                    why=why_instance_implies_its_constraints)

        return g

    def resolve(self, initial_module):
        self.constrain(initial_module)

        pgraph = self.create_pgraph()
        solution = solve(pgraph)

        return [instance
                for optuple, instance in iteritems(self._instances_alive)
                if solution[pgraph.node_for(optuple)]]


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
        # Mix context specific instance type into a module class.
        type_dict = dict(__module__ = module.__module__,
                         __doc__    = module.__doc__,
                         _module    = module,
                         _context   = context)
        bases = (module, context.module_mixin)

        return type(module.__name__, bases, type_dict)

    @classmethod
    def _create_domain(cls, module):
        return module._opmake(set(optype._values)
                              for optype in module._optypes)

    def init_pgraph(self, g):
        atom_for_module = partial(g.atom_for, self.module)
        module_atom = atom_for_module()

        for option, values in self.domain._iterpairs():
            atom_for_option = partial(atom_for_module, option)

            option_node = AtMostOne(g, map(atom_for_option, values),
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
        if option is not None:
            return self.new_node(OptionValueAtom, module, option, value)
        else:
            return self.new_node(ModuleAtom, module)

    def node_for(self, mslice):
        # TODO should accept arbitrary expr as well.
        return self.new_node(OptupleNode, mslice())


@ContextPgraph.node_type
class ModuleAtom(Atom):

    def __init__(self, module):
        super(ModuleAtom, self).__init__()
        self.module = module

        self[False].level = 0  # first of all, try not to build a module

    def __repr__(self):
        return repr(self.module)


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
class OptupleNode(And):

    _optimize_new = True

    @classmethod
    def _new(cls, optuple):
        new_atom = partial(cls.pgraph.atom_for, optuple._module)
        option_atoms = tuple(starmap(new_atom, optuple._iterpairs()))

        if not option_atoms:
            return cls.pgraph.atom_for(optuple._module)
        else:
            return super(OptupleNode, cls)._new(option_atoms, optuple)

    def __init__(self, option_atoms, optuple):
        super(OptupleNode, self).__init__(option_atoms,
                why_identity_implies_all_operands_identity=None,  # TODO
                why_all_operands_identity_implies_identity=None)  # TODO

        self.optuple = optuple

    def __repr__(self):
        return repr(self.optuple)


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

def why_instance_implies_its_constraints(outcome, cause):
    node, value = outcome
    what = ('enabled as a dependence' if value else
            'disabled as a dependent')
    fmt = '{node} is {what} of {cause.node}'
    return fmt.format(**locals())

def why_inviable_instance_is_disabled(outcome, *_):
    node, value = outcome
    assert not value
    fmt = '{node} is disabled because of an error: {node.error}'
    return fmt.format(**locals())


def resolve(initial_module, module_mixin=object):
    return Context(module_mixin).resolve(initial_module)


if __name__ == '__main__':
    import util
    util.init_logging(filename='%s.log' % __name__)

    from pprint import pprint

    from mybuild.binding.pydsl import *

    @module
    def conf(self):
        self._constrain(m1(bar=17))
        # self._constrain(m3)
        self.sources = 'test.c'

    @module
    def m1(self, bar=42):
        self._constrain(m2(foo=bar))

    @module
    def m2(self, foo=42):
        if foo == 42:
            raise InstanceError('FUUU')

    @module
    def m3(self):
        pass

    instances = resolve(conf)

    pprint(instances)
