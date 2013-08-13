"""
Pgraph solver.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-30"

__all__ = [
    "solve",
    "SolveError",
]


from _compat import *

from collections import defaultdict
import operator

from mybuild.pgraph import *
from mybuild.rgraph import *

from util.itertools import pop_iter
from util.operator import getter
from util.operator import invoker

import util, logging
logger = util.get_extended_logger(__name__)


def log_debug_enabled(logger=logger):
    return logger.isEnabledFor(logging.DEBUG)


class Solution(object):
    """
    Solution backed by sets of nodes and their literals.
    """

    _dump_attrs = 'valid nodes literals'.split()# + ['reasons']

    @property
    def valid(self):
        return len(self.nodes) == len(self.literals)

    def __init__(self):
        super(Solution, self).__init__()

        self.nodes    = set()
        self.literals = set()
        self.reasons  = set()

    def dispose(self):
        del self.nodes
        del self.literals
        del self.reasons

    def update(self, other, ignore_errors=False):
        self.nodes    |= other.nodes
        self.literals |= other.literals
        self.reasons  |= other.reasons

        self._error_check(ignore_errors)

    def difference_update(self, other, ignore_errors=False):
        self.nodes    -= other.nodes
        self.literals -= other.literals
        self.reasons  -= other.reasons

        self._error_check(ignore_errors)

    def _error_check(self, ignore_errors=False):
        if not ignore_errors and not self.valid:
            raise SolutionError(self)


class Trunk(Solution):
    """docstring for Trunk"""

    _dump_attrs = (Solution._dump_attrs +
                   'branchmap dead_branches neglefts'.split())

    def __init__(self):
        super(Trunk, self).__init__()

        self.branchmap     = dict()  # maps gen literals to branches
        self.dead_branches = dict()  # gen literals to dead branches

        self.neglefts = dict()   # neglasts to sets of left literals

    def update(self, diff, ignore_errors=False):
        if self is not diff.trunk:
            raise ValueError('Diff must be created from this trunk')

        assert self.literals.isdisjoint(diff.literals), \
                "diff must not intersect the trunk (must be a strict diff)"

        for neglast, negexcl in iteritems(diff.negexcls):
            self.neglefts[neglast] -= negexcl

        super(Trunk, self).update(diff, ignore_errors)

    def difference_update(self, other, ignore_errors=False):
        raise NotImplementedError('Unsupported operation')

    def substitute_branch(self, branch, other):
        """
        Replaces a branch by another one by updating gen_literals of the other
        and a branchmap of self.
        """
        if branch is other:
            raise ValueError("Can't substitute branch with itself")
        if not (self is branch.trunk is other.trunk):
            raise ValueError("Both branches must be created from this trunk")

        other.gen_literals |= branch.gen_literals

        assert branch.valid or not other.valid

        # Even if other is not valid, use a branchmap for branch.
        branchmap = (self.branchmap if branch.valid else
                     self.dead_branches)

        # Fixup any references to this one.
        for gen_literal in branch.gen_literals:
            assert branchmap[gen_literal] is branch
            branchmap[gen_literal] = other

    def iter_branch_todo_away(self, branch, ignore_errors=False):
        if self is not branch.trunk:
            raise ValueError("Branch must be created from this trunk")

        for literal in branch.iter_todo_away():
            try:
                implied = self.branchmap[literal]

            except KeyError:
                if literal in self.literals:
                    continue  # included in the trunk, i.e. unconditionally
                assert ~literal in self.literals

                if not ignore_errors:
                    raise SolutionError(branch)

                # If ~literal was added into trunk by create_trunk, then
                # there is no branch for literal, even dead.
                # Give up in this case and yield None.
                implied = self.dead_branches.get(literal)

            yield literal, implied

    def branchset(self):
        return set(itervalues(self.branchmap))


class Diff(Solution):
    """docstring for Diff"""

    _dump_attrs = (Solution._dump_attrs + 'todo negexcls'.split())

    @property
    def trunked(self):
        return self.trunk is not None

    @property
    def ready(self):
        return not self.todo

    def __init__(self, trunk):
        super(Diff, self).__init__()

        self.trunk = trunk

        self.todo = set()  # literals
        self.negexcls = defaultdict(set)  # {neglast: literals...}

    def dispose(self):
        self.trunk = None
        del self.todo
        del self.negexcls
        super(Diff, self).dispose()

    def flatten(self):
        if not self.ready:
            raise NotImplementedError('not ready: {0}: {0.todo}'.format(self))

        ret = Solution()
        ret.update(self.trunk)
        ret.update(self)
        assert ret.valid == self.valid

        return ret

    def _check_capable(self, other):
        if self.trunk is not other.trunk:
            raise ValueError('Both diffs must belong to the same trunk')
        if not other.ready:
            raise NotImplementedError('not ready: {0}: {0.todo}'.format(other))

    def update(self, other, ignore_errors=False):
        self._check_capable(other)

        for neglast, negexcl in iteritems(other.negexcls):
            assert self.trunk.neglefts[neglast] >= negexcl
            self.__do_neglast(neglast, operator.__ior__, negexcl)

        super(Diff, self).update(other, ignore_errors)

    def difference_update(self, other, ignore_errors=False):
        self._check_capable(other)

        for neglast, negexcl in iteritems(other.negexcls):
            self.__do_neglast(neglast, operator.__isub__, negexcl)

        super(Diff, self).difference_update(other, ignore_errors)

    def add_literal(self, literal, ignore_errors=False):
        for neglast in literal.neglasts:
            self.__do_neglast(neglast, invoker.add(literal))

        if literal not in self.trunk.literals:
            self.literals.add(literal)
        if literal.node not in self.trunk.nodes:
            self.nodes.add(literal.node)

        self._error_check(ignore_errors)

    def sync_with_trunk(self, ignore_errors=False):
        """Keep self a strict diff with the trunk."""
        trunk = self.trunk

        for neglast in self.negexcls:
            self.__do_neglast(neglast, operator.__isub__,
                              neglast.literals-trunk.neglefts[neglast])

        super(Diff, self).difference_update(trunk, ignore_errors)

    def __do_neglast(self, neglast, op=None, *args):
        trunk_negleft = self.trunk.neglefts[neglast]
        negexcl = self.negexcls[neglast]

        if op is not None:
            op(negexcl, *args)  # TODO don't like this

        assert trunk_negleft >= negexcl, (
                "branch: %r; neglast: %r; negexcl %r must be subset of trunk negleft %r" %
                (self, neglast.literals, negexcl, trunk_negleft))

        left = len(trunk_negleft) - len(negexcl)
        if left <= 1:
            negleft = (trunk_negleft-negexcl) if left else ()

            neg_literal, neg_reason = neglast.neg_reason_for(*negleft)

            self.reasons.add(neg_reason)
            self.todo.add(neg_literal)

    def iter_todo_away(self):
        return filternot(self.literals.__contains__, pop_iter(self.todo))

    def __repr__(self):
        return ('<{cls.__name__}: {nr_todos} todo ({state})>'
                .format(cls=type(self),
                        nr_todos=len(self.todo),
                        state='valid' if self.valid else 'dead'))


class Branch(Diff):
    """docstring for Branch"""

    _dump_attrs = (Diff._dump_attrs + 'gen_literals'.split())

    @property
    def valid(self):
        return self.error is None and len(self.nodes) == len(self.literals)

    def __init__(self, trunk, gen_literal):
        super(Branch, self).__init__(trunk)
        self.gen_literals = set()

        self.error = None
        self.gen_literals.add(gen_literal)

        self.add_literal(gen_literal)

        self.reasons |= gen_literal.imply_reasons
        self.todo    |= gen_literal.implies

    def update(self, other, ignore_errors=False):
        if self.literals >= other.gen_literals:  # other is already in self
            assert self.nodes    >= other.nodes
            assert self.literals >= other.literals
            assert self.reasons  >= other.reasons
            assert self.todo     >= other.todo
            assert all(self.negexcls[neglast] >= negexcl
                       for neglast, negexcl in iteritems(other.negexcls))
            return

        super(Branch, self).update(other, ignore_errors)

    def __repr__(self):
        try:
            return ('<{cls.__name__}: {nr_todos} todo ({state}) {gen_list!r}>'
                    .format(cls=type(self),
                            gen_list=list(self.gen_literals),
                            nr_todos=len(self.todo),
                            state='valid' if self.valid else 'dead'))
        except AttributeError:
            return '<{cls.__name__}: DISPOSED>'.format(cls=type(self))


@logger.wrap
def create_trunk(pgraph, initial_literals=[]):
    initial_literals = to_lset(initial_literals)

    logger.info('creating trunk for %d node(s)', len(initial_literals))
    if log_debug_enabled():
        for literal in initial_literals:
            logger.debug('\tinitial literal: %r', literal)

    trunk = Trunk()

    nodes    = trunk.nodes
    literals = trunk.literals
    reasons  = trunk.reasons
    neglefts = trunk.neglefts

    neg_todo = list()

    for node in pgraph.nodes:
        for literal in node:
            for neglast in literal.neglasts:
                negleft = neglefts[neglast] = set(neglast.literals)

                if len(negleft) <= 1:  # will not happen, generally speaking
                    logger.warning('len(negleft) <= 1')
                    neg_todo.append((neglast, negleft))

    # During the loop below we admit possible violation of the main context
    # invariant, i.e. len(nodes) may become less than len(literals).
    #
    # A difference between implication closures of conflicting literals is
    # accumulated in order to be able to produce better error reporting
    # because of keeping more reason chains for all literals.
    todo = initial_literals
    todo.update(pgraph.const_literals)

    for literal in todo:
        reasons.add(Reason(None, literal))

    literals |= todo

    for literal in pop_iter(todo):
        logger.debug('\ttrunk literal: %r', literal)

        assert literal in literals, "must has already been added"
        nodes.add(literal.node)

        reasons |= literal.imply_reasons

        for neglast in literal.neglasts:
            negleft = neglefts[neglast]
            negleft.remove(literal)  # must be still there, raises otherwise

            if len(negleft) == 1:
                # defer negating the last literal,
                # cause it still may be excluded.
                neg_todo.append((neglast, negleft))

        newly_seen = literal.implies - literals

        if not todo and not newly_seen:
            # no more direct implications, flush neg_todo
            for neglast, negleft in neg_todo:
                logger.debug('\ttrunk negleft: %r', negleft)

                assert len(negleft) <= 1, "at most one literal must have left"
                neg_literal, neg_reason = neglast.neg_reason_for(*negleft)

                if neg_literal not in literals:
                    newly_seen.add(neg_literal)

                reasons.add(neg_reason)

            del neg_todo[:]

        literals |= newly_seen
        todo     |= newly_seen

    if not trunk.valid:
        logger.info('trunk is not valid')
        for node in filter(trunk.literals.issuperset, trunk.nodes):
            logger.info('\tviolated node: %r', node)

        raise SolutionError(trunk)

    logger.info('created trunk with %d node(s)', len(trunk.nodes))

    unresolved_nodes = (pgraph.nodes - trunk.nodes)
    logger.info('preparing branchmap for %d node(s)', len(unresolved_nodes))

    for node in unresolved_nodes:
        logger.debug('\tunresolved node: %r', node)

        for literal in node:
            trunk.branchmap[literal] = Branch(trunk, literal)

    assert len(trunk.branchmap) == 2*len(unresolved_nodes)

    logger.dump(trunk)
    return trunk


def expand_branch(branch, ignore_errors=False):
    """Handles all branch todos (if any), in other words makes it ready.

    Implementation of non-recursive DFS."""
    if branch.ready:
        return

    trunk = branch.trunk

    stack = list()

    def stack_push(branch):
        assert not hasattr(branch, 'todo_it'), ("A branch has 'todo_it' attr "
                                                "iff it is already in stack")
        branch.todo_it = trunk.iter_branch_todo_away(branch, ignore_errors)
        stack.append(branch)

    def stack_pop():
        branch = stack.pop()
        del branch.todo_it
        return branch

    stack_push(branch)

    while stack:
        branch = stack[-1]

        log_indent = '. '*len(stack)
        logger.debug('\t%shandling  %r', log_indent, branch)

        try:
            literal, implied = next(branch.todo_it)
            logger.debug('\t%stodo literal: %r, implied: %r', log_indent,
                         literal, implied)

            if implied is None:
                assert ignore_errors
                branch.add_literal(literal, ignore_errors)
                continue

            if not ignore_errors and not implied.valid:
                logger.debug('\t%s(implied is not valid: %r)', log_indent,
                             implied)
                branch.todo.add(literal)  # it was NOT handled, save it back
                raise SolutionError(branch)

            if implied.ready:
                branch.update(implied, ignore_errors)
                continue

            if hasattr(implied, 'todo_it'):  # equivalent (mutual implication)
                logger.debug('\t%s(mutual implication with %r)', log_indent,
                             implied)
                implied.todo |= branch.todo
                branch.todo.clear()  # otherwise update() would refuse it

                try:
                    implied.update(branch, ignore_errors)
                finally:
                    trunk.substitute_branch(branch, implied)
                    branch.dispose()  # make gc happy

                raise StopIteration  # forget about this branch

        except SolutionError as error:
            assert not ignore_errors, "Hey, no errors when ignore_errors=True!"
            logger.debug('\t%sinviable  %r', log_indent, branch)

            # unwind implication stack
            for implicant in pop_iter(stack, pop=stack_pop):
                implicant.error = error
                error = SolutionError(implicant, error)

        except StopIteration:
            logger.debug('\t%ssucceeded %r', log_indent, branch)

            # no more implications, or the branch was merged into an equivalent
            stack_pop()

        else:  # defer until a branch is initialized
            logger.debug('\t%sdeferred  %r', log_indent, branch)
            #
            # During initialization of the implied branch it may have been
            # replaced by an implicant (appears upper on the stack).
            #
            # Example:
            #   A => B => C => A
            #           ^- assuming we're handling this implication now
            #
            # Upon returning back to handling the implication, a branch
            # initially created for C gets replaced by A and should not be
            # used anymore.
            #
            # So the best thing we can do here is to restart handling the
            # literal from the beginning.
            branch.todo.add(literal)

            # what to handle next
            stack_push(implied)


def expand_branchset(trunk, ignore_errors=False):
    branchset = trunk.branchset()

    if ignore_errors:
        dead_branchset = set(itervalues(trunk.dead_branches))
        for branch in dead_branchset:
            branch.sync_with_trunk(ignore_errors=True)
        branchset.update(dead_branchset)

    for branch in filter(getter.trunked, branchset):
        expand_branch(branch, ignore_errors)


def branchset_to_resolve(trunk):
    dead_literals = set()
    for branch in filternot(getter.valid, trunk.branchset()):
        dead_literals |= branch.gen_literals
    return set(trunk.branchmap[~literal] for literal in dead_literals)


@logger.wrap
def resolve_branches(trunk, branches=None):
    """
    Merges given branches back into trunk updating its branchmap and rest
    branches.
    """
    if branches is None:
        branches = branchset_to_resolve(trunk)

    logger.dump(trunk)

    while branches:
        logger.info('resolving %d branch(es)', len(branches))

        resolved = Diff(trunk)  # a patch created by merging together all diffs

        for branch in branches:
            logger.debug('\tmerging: %r', branch)
            resolved.update(branch)
        expand_branch(resolved)  # handle todos, if any

        # reintegrate it back into trunk (cannot fail, always succeeds)
        trunk.update(resolved)

        # remove resolved branches and their opposites from branchmap
        for literal in resolved.literals:
            del trunk.branchmap[literal]
            trunk.dead_branches[~literal] = trunk.branchmap.pop(~literal)

        # Maintain remaining branches to be strict diffs with just updated
        # trunk. This may involve new conflicts, i.e. new branches can be
        # resolved, so we'll create a new list of branches to resolve next.

        for branch in trunk.branchset():
            assert branch.valid, 'only valid branches must have left'
            branch.difference_update(resolved, ignore_errors=True)
        expand_branchset(trunk)

        logger.dump(trunk)

        branches = branchset_to_resolve(trunk)


@logger.wrap
def stepwise_resolve(trunk):
    levelmap = defaultdict(set)

    for literal, branch in iteritems(trunk.branchmap):
        if literal.level is not None:
            levelmap[literal.level].add(branch)

    for branchset in map(levelmap.get, sorted(levelmap)):
        resolve_branches(trunk, branchset & trunk.branchset())


def solve_trunk(pgraph, initial_values={}):
    trunk = create_trunk(pgraph, initial_values)

    expand_branchset(trunk)
    resolve_branches(trunk)
    stepwise_resolve(trunk)

    # to be called from rgraph
    expand_branchset(trunk, ignore_errors=True)

    return trunk


def solve(pgraph, initial_values={}):
    logger.info('solving %r with initials: %r', pgraph, initial_values)

    trunk = solve_trunk(pgraph, initial_values)

    # rgraph = Rgraph(trunk)
    # rgraph.print_graph() #prints a rgraph to console

    ret = dict.fromkeys(pgraph.nodes)
    ret.update(trunk.literals)
    logger.debug('Solution:')
    for literal in ret:
        logger.debug('\t%s: %s', literal, ret[literal])
    return ret


class SolveError(Exception):
    """docstring for SolveError"""

class SolutionError(SolveError):
    """docstring for SolutionError"""

    def __init__(self, context, cause=None):
        super(SolutionError, self).__init__()
        self.context = context
        self.cause = cause

