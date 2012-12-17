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

from core import *
from constraints import *
from expr import *
from util import singleton
from util import NotifyingMixin
import pdag

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

    def pnode_from(self, expr):
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

@Module.register_attr('_atom_type')
class ModuleAtom(pdag.Atom):
    __slots__ = ()

    def __str__(self):
        return self._module_name

    @classmethod
    def _new_type(cls, module_type, *ignored):
        return type('ModuleAtom_M%s' % (module_type._module_name,),
                    (cls, module_type),
                    dict(__slots__=()))


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

@Option.register_attr('_atom_type')
class OptionValueAtom(pdag.Atom):
    __slots__ = '_value'

    def __init__(self, value):
        super(OptionValueAtom, self).__init__()
        self._value = value

    def __str__(self):
        return '(%s.%s==%s)' % (self._module_name,
                                self._option_name, self._value)

    @classmethod
    def _new_type(cls, option_type):
        return type('OptionAtom_M%s_O%s' % (option_type._module_name,
                                            option_type._option_name),
                    (cls, option_type),
                    dict(__slots__=()))


@Module.register_attr('_instance_type')
class Instance(Module.Type):
    """docstring for Instance"""

    class _InstanceProxy(object):
        """docstring for _InstanceProxy"""
        __slots__ = '_owner_instance', '_optuple'

        def __init__(self, owner_instance, optuple):
            super(Instance._InstanceProxy, self).__init__()
            self._owner_instance = owner_instance
            self._optuple = optuple

        def __nonzero__(self):
            return self._owner_instance._decide(self._optuple)

        def __getattr__(self, attr):
            return self._owner_instance._decide_option(self._optuple, attr)

    def __init__(self, domain, optuple, constraints):
        """Private constructor. Use '_post_new' instead."""
        super(Instance, self).__init__()

        self._domain = domain
        self._optuple = optuple
        self._constraints = constraints

        with log.debug("mybuild: new %r", self):
            try:
                self._init_fxn(*optuple)
            except InstanceError as e:
                log.debug("mybuild: unviable %r: %s", self, e)
                raise e
            else:
                log.debug("mybuild: succeeded %r", self)

    @classmethod
    def _post_new(cls, domain, optuple, _constraints=None):
        if _constraints is None:
            _constraints = Constraints()
            # _constraints.constrain_mslice(optuple)

        def new():
            try:
                instance = cls(domain, optuple, _constraints)
            except InstanceError:
                pass
            else:
                domain.register(instance)

        domain.post(new)

    def ask(self, mslice):
        optuple = mslice._to_optuple()
        exprify_eval(optuple, self._domain.consider)
        return self._InstanceProxy(self, optuple)

    @singleton
    class _build_visitor(ExprVisitor):

        def visit(self, expr, constraints):
            expr = exprify(expr)
            # log.debug('mybuild: visit [%r] %r with %r',
            #           type(expr), expr, constraints)
            return ExprVisitor.visit(self,
                exprify_eval(expr, constraints.check), constraints)

        def visit_bool(self, expr, constraints):
            return (constraints,) if expr else ()

        def visit_Atom(self, expr, constraints, negated=False):
            try:
                expr.eval(constraints.constrain, negated=negated)
            except ConstraintError:
                return self.visit_bool(False, constraints)
            else:
                return self.visit_bool(True, constraints)

        def visit_Not(self, expr, constraints):
            return self.visit_Atom(expr.atom, constraints, negated=True)

        def visit_Or(self, expr, constraints):
            # disjuncion of disjunctions: (C1|C2) | ... | (CK|...|CN)
            # nothing special to do here, expand parens by flattening the list
            return tuple(chain.from_iterable(
                self.visit(e, constraints.new_branch()) for e in expr.operands))

        def visit_And(self, expr, constraints):
            # Important assumption:
            # 'expr.operands' first yields atomic expressions (atoms and
            # negations), and then compounds (disjunctions in this case).
            # This allows us to defer branching the 'constraints' as much as
            # possible, until it becomes really necessary.

            # conjuction of disjunctions: (C1|C2) & ... & (CK|...|CN)
            cj_of_djs = (self.visit(e, constraints) for e in expr.operands)

            # expand parens by merging constraint dicts to get the resulting
            # disjunction: C1&...&CK | C1&...&CN | C2&...&CK | C2&...&CN | ...
            def iter_multiply(djs):
                def uniquify_filter(djs):
                    """
                    Removes duplicates, filters out the parent constraints,
                    and yields non-empty iterables.
                    """
                    for dj in djs:
                        if not dj:
                            raise ConstraintError
                        if len(dj) == 1:
                            if dj[0] is not constraints:
                                yield dj
                        else:
                            constraints_by_id = dict((id(c), c) for c in dj)
                            del constraints_by_id[constraints]
                            if constraints_by_id:
                                yield constraints_by_id.itervalues()

                try:
                    djs_list = sorted(uniquify_filter(djs), key=len)
                except ConstraintError:
                    return

                if not djs_list:
                    yield constraints
                    return

                for new_cj in product(*djs_list):
                    try:
                        yield constraints.merge_children(new_cj)
                    except ConstraintError:
                        pass

            return tuple(iter_multiply(cj_of_djs))

    def _log_build_choices(self, name, choices):
        length = len(choices)
        log.debug('mybuild: got %d %s choice%s: %r',
            length, name, 's' if length != 1 else '', choices)

    def constrain(self, expr):
        expr = exprify_eval(expr, self._domain.consider)

        with log.debug('mybuild: constrain %r', expr):
            choices = self._build_visitor.visit(expr, self._constraints)
            self._log_build_choices('constrain', choices)

            self._constraints = self._take_one_spawn_rest(choices)

    def _decide(self, expr):
        expr = exprify(expr)

        with log.debug('mybuild: deciding bool(%r)', expr):
            visit = self._build_visitor.visit

            yes_choices = visit(expr, self._constraints.new_branch())
            self._log_build_choices('"yes"', yes_choices)

            no_choices = visit(~expr, self._constraints.new_branch())
            self._log_build_choices('"no"', no_choices)

            ret = bool(yes_choices)
            choices = no_choices, yes_choices

            self._constraints = self._take_one_spawn_rest(choices[ret])
            self._spawn_all(choices[not ret])

            log.debug('mybuild: return %s', ret)
            return ret

    def _decide_option(self, optuple, option):
        module = optuple._module

        with log.debug('mybuild: deciding %r.%s', optuple, option):
            if not hasattr(optuple, option):
                raise AttributeError("'%s' module has no attribute '%s'" %
                    (module._name, option))

            try:# to get an already constrained exact value (if any).
                # This is the way of how spawned instances get an option
                # which caused the spawning.
                ret_value = self._constraints.get(module, option)
            except ConstraintError:
                pass
            else:
                log.debug('mybuild: return %r', ret_value)
                return ret_value

            # Option without the module itself is meaningless. Fail-fast way
            # for case when the whole module has been previously excluded.
            self.constrain(module)

            octx = self._domain.domain_for(module, option)

            octx.subscribe(partial(self._branch_and_spawn,
                                   self._constraints, module, option))
            # after that one shouldn't touch self._constraints anymore
            self._constraints.freeze()

            def constrain_all(values):
                constrain = self._constraints.constrain
                for value in values:
                    try:
                        yield constrain(module, option, value, branch=True)
                    except ConstraintError:
                        pass

            self._constraints = self._take_one_spawn_rest(constrain_all(octx))

            ret_value = self._constraints.get(module, option) # must not throw

            log.debug('mybuild: return %r', ret_value)
            return ret_value

    def _branch_and_spawn(self, constraints, module, option, value):
        log.debug('mybuild: branch %r with %r by %r.%s = %r',
            self._optuple, constraints, module, option, value)

        try:
            constraints = constraints.constrain(module, option, value,
                branch=True)
        except ConstraintError as e:
            log.debug('mybuild: branch error: %s', e)
            pass
        else:
            log.debug('mybuild: branch OK')
            self._spawn(constraints)

    def _take_one_spawn_rest(self, constraints_iterable):
        constraints_it = iter(constraints_iterable)

        try: # Retrieve the first one (if any) to return it.
            ret_constraints = constraints_it.next()
        except StopIteration:
            raise InstanceError('No viable choice to take')
        else:
            log.debug('mybuild: take %r', ret_constraints)

        # Spawn for the rest ones.
        self._spawn_all(constraints_it)

        return ret_constraints

    def _spawn_all(self, constraints_iterable):
        for constraints in constraints_iterable:
            self._spawn(constraints)

    def _spawn(self, constraints):
        log.debug('mybuild: spawn %r', constraints)
        self._post_new(self._domain, self._optuple, constraints)

    def __repr__(self):
        return '<Instance %r with %r>' % (self._optuple, self._constraints)

    @classmethod
    def _new_type(cls, module_type, fxn):
        return type('Instance_M%s' % (module_type._module_name,),
                    (cls, module_type),
                    dict(__slots__=(), _init_fxn=fxn))


def build(conf_module):
    domain = Context()
    conf_domain = domain.domain_for(conf_module)

    assert len(conf_domain._instances) == 1
    conf_instance_set = conf_domain._instances.itervalues().next()

    assert len(conf_instance_set) == 1
    conf_instance = iter(conf_instance_set).next()

    constraints = conf_instance._constraints # XXX

    # flat_constr = constraints.branch().flatten()
    # for m in flat_constr._dict:
    #     ctx = self._modules[m]
    #     for mslice, inst_set in ctx._instances:
    #         if flat_constr.check_mslice(mslice) is not False:


    # try:
    #     constraints = Constraints.merge(instance._constraints
    #                                     for instance in domain._instances)
    # except Exception, e:
    #     raise e

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

    build(conf)

