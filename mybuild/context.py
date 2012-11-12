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

import logs as log


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

    def consider(self, optuple):
        self.context_for(optuple._module).consider(optuple)

    def register(self, instance):
        self.context_for(instance._module).register(instance)

    def context_for(self, module, option=None):
        try:
            context = self._modules[module]
        except KeyError:
            with self.reent_lock():
                context = self._modules[module] = ModuleContext(self,module)

        return context


class ModuleContext(object):
    """docstring for ModuleContext"""

    def __init__(self, build_ctx, module):
        super(ModuleContext, self).__init__()

        self.build_ctx = build_ctx
        self.module = module

        options = module._options
        self.vsets = options._make(OptionContext() for _ in options)

        self.instances = defaultdict(set) # { optuple : { instances... } }

        for a_tuple in izip_longest(*(o._values for o in options),
                                    fillvalue=Ellipsis):
            self.consider(a_tuple)

    def consider(self, optuple):

        what_to_extend = ((vset,v) for vset,v in izip(self.vsets, optuple)
                          if v is not Ellipsis and v not in vset)

        for vset_to_extend, value in what_to_extend:
            self._extend_vset(vset_to_extend, (value,))

    def _extend_vset(self, vset_to_extend, values):
        log.debug('mybuild: extending %r with %r', vset_to_extend, values)
        vset_to_extend |= values

        vsets_optuple = self.vsets

        sliced_vsets = (vset if vset is not vset_to_extend else values
                        for vset in vsets_optuple)

        for new_tuple in product(*sliced_vsets):
            self.module._instance_type._post_new(self.build_ctx,
                vsets_optuple._make(new_tuple))

    def register(self, instance):
        self.instances[instance._optuple].add(instance)

    def vset_for(self, option):
        return getattr(self.vsets, option)


class OptionContext(MutableSet):
    """docstring for OptionContext"""

    def __init__(self):
        super(OptionContext, self).__init__()
        self._set = set()
        self._subscribers = []
        self._subscribers_keys = set() # XXX

    def add(self, value):
        if value in self:
            return
        self._set.add(value)

        subscribers = self._subscribers
        self._subscribers = None # our methods are not reenterable

        for s in subscribers:
            s(value)

        self._subscribers = subscribers

    def discard(self, value):
        if value not in self:
            return
        raise NotImplementedError

    def subscribe(self, key, fxn):
        assert key not in self._subscribers_keys
        self._subscribers_keys.add(key)
        self._subscribers.append(fxn)

    def __iter__(self):
        return iter(self._set)
    def __len__(self):
        return len(self._set)
    def __contains__(self, value):
        return value in self._set

    def __repr__(self):
        return '<OptionContext %r>' % (self._set,)


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
            if attr.startswith('_'):
                return object.__getattr__(attr)

            return self._owner_instance._decide_option(self._optuple, attr)

    def __init__(self, build_ctx, optuple, constraints):
        """Private constructor. Use '_post_new' instead."""
        super(Instance, self).__init__()

        self._build_ctx = build_ctx
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
    def _post_new(cls, build_ctx, optuple, _constraints=None):
        if _constraints is None:
            _constraints = Constraints()

        def new():
            try:
                instance = cls(build_ctx, optuple, _constraints)
            except InstanceError:
                pass
            else:
                build_ctx.register(instance)

        build_ctx.post(new)

    def ask(self, mslice):
        optuple = mslice._to_optuple()
        self._build_ctx.consider(optuple)
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
                self.visit(e, constraints.fork()) for e in expr.operands))

        def visit_And(self, expr, constraints):
            # Important assumption:
            # 'expr.operands' first yields atomic expressions (atoms and
            # negations), and then compounds (disjunctions in this case).
            # This allows us to defer forking the 'constraints' as much as
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
        with log.debug('mybuild: constrain %r', expr):
            choices = self._build_visitor.visit(expr, self._constraints)
            self._log_build_choices('constrain', choices)

            self._constraints = self._take_one_spawn_rest(choices)

    def _decide(self, expr):
        expr = exprify(expr)

        with log.debug('mybuild: deciding bool(%r)', expr):
            visit = self._build_visitor.visit

            yes_choices = visit(expr, self._constraints.fork())
            self._log_build_choices('"yes"', yes_choices)

            no_choices = visit(~expr, self._constraints.fork())
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

            ctx = self._build_ctx.context_for(module)
            vset = ctx.vset_for(option)

            vset.subscribe(self, partial(self._fork_and_spawn,
                self._constraints, module, option))
            # after that one shouldn't touch self._constraints anymore
            self._constraints.freeze()

            def constrain_all(values):
                constrain = self._constraints.constrain
                for value in values:
                    try:
                        yield constrain(module, option, value, fork=True)
                    except ConstraintError:
                        pass

            self._constraints = self._take_one_spawn_rest(constrain_all(vset))

            ret_value = self._constraints.get(module, option) # must not throw

            log.debug('mybuild: return %r', ret_value)
            return ret_value

    def _fork_and_spawn(self, constraints, module, option, value):
        log.debug('mybuild: fork %r with %r by %r.%s = %r',
            self._optuple, constraints, module, option, value)

        try:
            constraints = constraints.constrain(module, option, value,
                fork=True)
        except ConstraintError as e:
            log.debug('mybuild: fork error: %s', e)
            pass
        else:
            log.debug('mybuild: fork OK')
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
        self._post_new(self._build_ctx, self._optuple, constraints)

    def __repr__(self):
        return '<Instance %r with %r>' % (self._optuple, self._constraints)

    @classmethod
    def _new_type(cls, module_type, fxn):
        return type('Instance_M%s' % (module_type._module_name,),
                    (cls, module_type),
                    dict(__slots__=(), _init_fxn=fxn))

