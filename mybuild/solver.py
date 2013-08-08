"""
Pgraph solver.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-30"

__all__ = [
    "solve",
    "SolveError",
]


from collections import defaultdict
import operator

from .pgraph import *
from .rgraph import *

from util.itertools import pop_iter
from util.compat import *

import logging
logger = logging.getLogger(__name__)


class Solution(object):
    """
    Solution backed by sets of nodes and their literals.
    """

    @property
    def valid(self):
        return len(self.nodes) == len(self.literals)

    def __init__(self):
        super(Solution, self).__init__()

        self.nodes    = set()
        self.literals = set()
        self.reasons  = set()

    def copy(self):
        cls = type(self)
        new = cls.__new__(cls)

        new.nodes    = self.nodes    .copy()
        new.literals = self.literals .copy()
        new.reasons  = self.reasons  .copy()

        return new

    def __len__(self):
        return len(self.literals)

    def __ior__(self, other):
        self.nodes    |= other.nodes
        self.literals |= other.literals
        self.reasons  |= other.reasons

        return self

    def __or__(self, other):
        ret = self.copy()
        ret |= other
        return ret

    def __isub__(self, other):
        self.nodes    -= other.nodes
        self.literals -= other.literals
        self.reasons  -= other.reasons

        return self

    def clear(self):
        self.nodes    .clear()
        self.literals .clear()
        self.reasons  .clear()

    def dispose(self):
        del self.nodes
        del self.literals
        del self.reasons

    def update(self, other, ignore_errors=False):
        self |= other

        if not ignore_errors and not self.valid:
            raise SolutionError(self)

    def difference_update(self, other, check=True):
        self -= other

        if check and not self.valid:
            raise SolutionError(self)

    def add_literal(self, literal, reason=None):
        self.literals .add(literal)
        self.nodes    .add(literal.node)
        if reason is not None:
            self.reasons.add(reason)


class TrunkSolution(Solution):
    """docstring for TrunkSolution"""

    def __init__(self):
        super(TrunkSolution, self).__init__()

        self.branchmap = dict()  # maps gen literals to branches
        self.neglefts = dict()   # neglasts to sets of left literals

        self.violation_branches = {}

    def copy(self):
        new = super(TrunkSolution, self).copy()

        new.branchmap   = self.branchmap.copy()
        new.neglefts    = self.neglefts.copy()

        new.violation_branches = self.violation_branches.copy()

        return new

    def __ior__(self, branch):
        if self is not branch.trunk:
            raise ValueError('Branch must belong to this trunk')

        for neglast, negexcl in iteritems(branch.negexcls):
            self.neglefts[neglast] -= negexcl

        return super(TrunkSolution, self).__ior__(branch)

    def __isub__(self, other):
        return NotImplemented

    def branchset(self):
        return set(itervalues(self.branchmap))


class BranchSolutionBase(Solution):
    """docstring for BranchSolutionBase"""

    def is_implied_by(self, other):
        raise NotImplementedError('Not implemented in base class')

    def __init__(self, trunk):
        super(BranchSolutionBase, self).__init__()

        self.trunk        = trunk

        self.todo         = set()  # literals
        self.negexcls     = defaultdict(set)  # {neglast: literals...}

    def copy(self):
        new = super(BranchSolutionBase, self).copy()

        new.trunk         = self.trunk

        new.todo = self.todo.copy()
        negexcls = new.negexcls = defaultdict(set)
        for neglast, negexcl in iteritems(self.negexcls):
            negexcls[neglast] = negexcl.copy()

        return new

    def __ior__(self, other):
        if self.trunk is not other.trunk:
            raise ValueError('Both branches must belong to the same trunk')
        if other.todo:
            raise NotImplementedError('Other is not ready')

        if other.is_implied_by(self):
            assert self.nodes    >= other.nodes
            assert self.literals >= other.literals
            assert self.reasons  >= other.reasons
            assert self.todo     >= other.todo
            for neglast, negexcl in iteritems(other.negexcls):
                assert self.negexcls[neglast] >= negexcl
            return self

        for neglast, negexcl in iteritems(other.negexcls):
            self.__do_neglast(neglast, operator.__ior__, negexcl)

        return super(BranchSolutionBase, self).__ior__(other)

    def __isub__(self, other):
        if self.trunk is not other.trunk:
            raise ValueError('Both branches must belong to the same trunk')
        if other.todo:
            raise NotImplementedError('Other is not ready')

        for neglast, negexcl in iteritems(other.negexcls):
            self.__do_neglast(neglast, operator.__isub__, negexcl)

        return super(BranchSolutionBase, self).__isub__(other)

    def update(self, other, ignore_errors=False, handle_todos=False):
        super(BranchSolutionBase, self).update(other, ignore_errors=ignore_errors)
        if handle_todos:
            self.handle_todos(ignore_errors=ignore_errors)

    def difference_update(self, other, ignore_errors=False, handle_todos=False):
        super(BranchSolutionBase, self).difference_update(other, ignore_errors=ignore_errors)
        if handle_todos:
            self.handle_todos(ignore_errors=ignore_errors)

    def substitute_with(self, other):
        raise NotImplementedError('Not implemented in base class')

    def clear(self):
        self.todo     .clear()
        self.negexcls .clear()
        super(BranchSolutionBase, self).clear()

    def dispose(self):
        del self.todo
        del self.negexcls
        super(BranchSolutionBase, self).dispose()

    def add_literal(self, literal, reason=None):
        for neglast in literal.neglasts:
            self.__do_neglast(neglast, operator.methodcaller('add', literal))

        super(BranchSolutionBase, self).add_literal(literal, reason)

    def __do_neglast(self, neglast, op, *args):
        negleft = self.trunk.neglefts[neglast]
        negexcl = self.negexcls[neglast]

        op(negexcl, *args)  # TODO don't like this

        left = len(negleft) - len(negexcl)
        if left <= 1:
            neg_literal, neg_reason = neglast.neg_reason_for(
                last_literal=(negleft-negexcl).pop() if left else None)

            self.reasons.add(neg_reason)
            self.todo.add(neg_literal)

    def iter_todo_away(self, ignore_errors=False):
        trunk = self.trunk

        for literal in pop_iter(self.todo):
            if literal in self.literals:
                continue  # already handled

            try:
                implied = trunk.branchmap[literal]

            except KeyError:
                if literal in trunk.literals:
                    continue  # included in the trunk, i.e. unconditionally

                assert ~literal in trunk.literals
                if not ignore_errors:
                    raise SolutionError(self)
                else:
                    if literal in trunk.violation_branches:
                        implied = trunk.violation_branches[literal]
                    else:
                        implied = None

            yield literal, implied

    def handle_todos(self, ignore_errors=False):
        """
        Must only be called when all branches in trunk.branchmap are
        completely initialized.
        """
        for literal, implied in self.iter_todo_away(ignore_errors=ignore_errors):
            if self.is_implied_by(implied):
                self.substitute_with(implied)
                break

            self.update(implied, ignore_errors=ignore_errors)

class BranchSolution(BranchSolutionBase):
    """docstring for BranchSolution"""

    @property
    def valid(self):
        return self.error is None and len(self.nodes) == len(self.literals)

    @property
    def initialized(self):
        return not self.todo

    def is_implied_by(self, other):
        return self.gen_literals <= other.literals

    def __init__(self, trunk, gen_literal):
        super(BranchSolution, self).__init__(trunk)
        self.gen_literals = set()

        self.error = None
        self.gen_literals.add(gen_literal)

        self.add_literal(gen_literal)

        self.reasons |= gen_literal.imply_reasons
        self.todo    |= gen_literal.implies

    def __invert__(self):
        try:
            any_gen = next(iter(self.gen_literals))
            inv_branch = self.trunk.branchmap[~any_gen]
        except (StopIteration, KeyError):
            assert False, 'should not happen'
        else:
            assert (not self.valid or not inv_branch.valid or
                    self.gen_literals == set(map(operator.__invert__,
                                                 inv_branch.gen_literals)))

        return inv_branch

    def copy(self):
        new = super(BranchSolution, self).copy()

        new.gen_literals = set()  # this is not copied
        new.error = None
        return new

    def substitute_with(self, other):
        """
        Upon replacement, this branch is disposed and must not be used anymore.
        """
        other.gen_literals |= self.gen_literals

        # Fixup any references to this one.
        for gen_literal in self.gen_literals:
            self.trunk.branchmap[gen_literal] = other

        self.dispose()  # make gc happy

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__,
                            ' & '.join(repr(literal).join('()')
                                       for literal in self.gen_literals))

class ResolvedBranchSolution(BranchSolutionBase):
    def is_implied_by(self, other):
        return False

def create_trunk(pgraph, initial_literals=[]):
    initial_literals = to_lset(initial_literals)

    logger.info('creating trunk for %d nodes', len(initial_literals))
    if logger.isEnabledFor(logging.DEBUG):
        for literal in initial_literals:
            logger.debug('\tinitial literal: %r', literal)

    trunk = TrunkSolution()

    nodes    = trunk.nodes
    literals = trunk.literals
    reasons  = trunk.reasons
    neglefts = trunk.neglefts

    neglasts_todo = list()

    for node in pgraph.nodes:
        for literal in node:
            for neglast in literal.neglasts:
                negleft = neglefts[neglast] = set(neglast.literals)

                if len(negleft) <= 1:  # will not happen, generally speaking
                    logger.warning('len(negleft) <= 1')
                    neglasts_todo.append(neglast)

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
        logger.debug('\thandling literal: %r', literal)

        assert literal in literals, "must has already been added"
        nodes.add(literal.node)

        reasons |= literal.imply_reasons

        for neglast in literal.neglasts:
            negleft = neglefts[neglast]
            negleft.remove(literal)  # must be still there, raises otherwise

            if len(negleft) == 1:
                # defer negating the last literal,
                # cause it still may be excluded.
                neglasts_todo.append(neglast)

        newly_seen = literal.implies - literals

        if not todo and not newly_seen:
            # no more direct implications, flush neglasts_todo
            for neglast in neglasts_todo:
                neg_literal, neg_reason = neglast.neg_reason_for(
                        # at most one literal is contained in a negleft
                        *neglefts[neglast])

                if neg_literal not in literals:
                    newly_seen.add(neg_literal)

                reasons.add(neg_reason)

            del neglasts_todo[:]

        literals |= newly_seen
        todo     |= newly_seen

    if not trunk.valid:
        logger.info('trunk is not valid')
        for node in filter(trunk.literals.issuperset, trunk.nodes):
            logger.info('\tviolated node: %r', node)

        raise SolutionError(trunk)

    logger.info('created trunk with %d nodes', len(trunk.nodes))

    return trunk


def prepare_branches(trunk, unresolved_nodes, ignore_errors=False):
    """
    Non-recursive DFS.
    """

    logger.debug('preparing branches for %d nodes', len(unresolved_nodes))

    for node in unresolved_nodes:
        logger.debug('\tunresolved node: %r', node)

        for literal in node:
            branch = trunk.branchmap[literal] = BranchSolution(trunk, literal)
            branch.todo_it = None

    assert len(trunk.branchmap) == 2*len(unresolved_nodes)

    stack = list()

    def stack_push(branch):
        assert branch.todo_it is None
        branch.todo_it = branch.iter_todo_away(ignore_errors)
        stack.append(branch)

    def stack_pop():
        branch = stack.pop()
        branch.todo_it = None
        return branch

    todo_branches = trunk.branchset()

    while stack or todo_branches:
        if not stack:
            stack_push(todo_branches.pop())

        log_indent = '. '*len(stack)
        branch = stack[-1]

        try:
            # Can't use branch.handle_todos since some branches are in an
            # intermediate state. Manual iteration also makes it possible to
            # check for mutual implication more efficiently.
            literal, implied = next(branch.todo_it)

            if implied is None:
                continue

            if not ignore_errors and not implied.valid:
                branch.todo.add(literal)
                raise SolutionError(branch)

            if implied.initialized:
                branch.update(implied, ignore_errors=ignore_errors)
                continue

            if implied.todo_it is not None:  # Equivalent (mutual implication).
                implied.todo |= branch.todo
                branch.todo.clear()

                implied.update(branch, ignore_errors=ignore_errors)
                branch.substitute_with(implied)

                raise StopIteration  # forget about this branch

        except SolutionError as error:
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

            todo_branches.remove(implied)
            stack_push(implied)


def resolve_branches(trunk, branches):
    logger.debug('Branch resolving started')
    resolved = ResolvedBranchSolution(trunk)

    for branch in branches:
        resolved.update(branch, handle_todos=True)
    logger.debug('Resolved created')

    while resolved:
        trunk.update(resolved)

        for literal in resolved.literals:
            trunk.violation_branches[~literal] = trunk.branchmap[~literal]
            for each in literal.node:  # remove both literal and ~literal
                del trunk.branchmap[each]

        next_resolved = ResolvedBranchSolution(trunk)

        logger.debug('Unresolved branches updating')
        for branch in trunk.branchset():
            assert branch.valid, 'only valid branches must have left'

            try:
                branch.difference_update(resolved, handle_todos=True)

            except SolutionError:
                next_resolved.update(~branch, handle_todos=True)  # may raise as well
        logger.debug('Unresolved branches updated')

        resolved = next_resolved
    logger.debug('Branch resolving completed')

def stepwise_resolve(trunk):
    levelmap = defaultdict(set)

    for literal, branch in iteritems(trunk.branchmap):
        if literal.level is not None:
            levelmap[literal.level].add(branch)

    for branchset in map(levelmap.get, sorted(levelmap)):
        resolve_branches(trunk, branchset & trunk.branchset())


def get_trunk_solution(pgraph, initial_values={}):
    nodes = pgraph.nodes

    trunk = create_trunk(pgraph, initial_values)
    # for literal in trunk.literals:
    #     print 'trunk', literal

    prepare_branches(trunk, nodes-trunk.nodes, True)
    resolve_branches(trunk, (~branch for branch in trunk.branchset()
                             if not branch.valid))
    stepwise_resolve(trunk)

    return trunk


def solve(pgraph, initial_values={}):
    logger.debug('Start solving')
    nodes = pgraph.nodes

    logger.debug('Initial data:\n\tpgraph nodes:%s\n\tinitial values: %s', nodes, initial_values)
    trunk = get_trunk_solution(pgraph, initial_values)

    rgraph = Rgraph(trunk.literals, trunk.reasons, trunk.violation_branches.values())
    rgraph.print_graph() #prints a rgraph to console
    rgraph.find_shortest_ways() #fills fields length and parent, see rgraph.py

    ret = dict.fromkeys(nodes)
    ret.update(trunk.literals)
    logger.debug('Solution:')
    for literal in ret:
        logger.debug('\t%s - %s', literal, ret[literal])
    return ret


class SolveError(Exception):
    """docstring for SolveError"""

class SolutionError(SolveError):
    """docstring for SolutionError"""

    def __init__(self, context, cause=None):
        super(SolutionError, self).__init__()
        self.context = context
        self.cause = cause

