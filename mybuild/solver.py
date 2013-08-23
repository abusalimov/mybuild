"""
Pgraph solver.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-30"

__all__ = [
    "Solution",
    "Trunk",
    "Diff",
    "Branch",

    "create_trunk",
    "expand_branch",
    "expand_branchset",
    "resolve_branches",
    "stepwise_resolve",
    "solve_trunk",

    "solve",
    "SolveError",
]


from _compat import *

from collections import defaultdict
import operator

from mybuild.pgraph import *

from util.itertools import pop_iter
from util.operator import getter
from util.operator import invoker
from util.prop import cached_property

import util, logging
logger = util.get_extended_logger(__name__)


def log_debug_enabled(logger=logger):
    return logger.isEnabledFor(logging.DEBUG)


class Solution(object):
    """
    Solution backed by sets of nodes and their literals.
    """

    _dump_attrs = 'valid nodes literals'.split() + ['reasons']

    @property
    def valid(self):
        return len(self.nodes) == len(self.literals)

    def __init__(self, initial=None):
        super(Solution, self).__init__()

        self.nodes    = set()
        self.literals = set()
        self.reasons  = set()  # note that this set does NOT include reasons
                               # from each literal's imply_reasons set, only
                               # special (like for neglasts or assumptions).

        if initial is not None:
            self |= initial

    def dispose(self):
        del self.nodes
        del self.literals
        del self.reasons

    def __ior__(self, other):
        self.nodes    |= other.nodes
        self.literals |= other.literals
        self.reasons  |= other.reasons
        return self

    def __isub__(self, other):
        self.nodes    -= other.nodes
        self.literals -= other.literals
        self.reasons  -= other.reasons
        return self

    def isdisjoint(self, other):
        return (self.nodes    .isdisjoint(other.nodes) and
                self.literals .isdisjoint(other.literals) and
                self.reasons  .isdisjoint(other.reasons))

    def __eq__(self, other):
        if not isinstance(other, Solution):
            return NotImplemented
        return (self.nodes    == other.nodes and
                self.literals == other.literals and
                self.reasons  == other.reasons)


class Trunk(Solution):
    """docstring for Trunk"""

    _dump_attrs = (Solution._dump_attrs +
                   'branchmap dead_branches neglefts'.split())

    @cached_property
    def base(self):
        ret = Solution()

        ret |= self
        for diff in reversed(self.commits):
            ret -= diff

        return ret

    @property
    def rev(self):
        return len(self.commits)

    def __init__(self):
        super(Trunk, self).__init__()

        self.neglefts = dict()   # neglasts to sets of left literals

        self.branchmap     = dict()  # maps gen literals to branches
        self.dead_branches = dict()  # gen literals to dead branches

        self.commits = list()  # incremental diffs applied to the trunk

    def commit(self, diff):
        if self is not diff.trunk:
            raise ValueError('Diff must be created from this trunk')

        assert self.isdisjoint(diff), ("diff must not intersect the trunk "
                                       "(must be a strict diff)")

        for literal in diff.literals:
            if literal not in self.branchmap:
                continue
            
            del self.branchmap[literal]  # just remove

            refused_literal = ~literal
            refused_branch = self.branchmap.pop(refused_literal)
            self.dead_branches[refused_literal] = refused_branch

            # Remember the current revision to be able to reproduce the branch
            # later (for error reporting, e.g.).
            refused_branch.baserev = self.rev

        for neglast, negexcl in iteritems(diff.negexcls):
            self.neglefts[neglast] -= negexcl

        self |= diff

        self.commits.append(diff)  # self.rev gets incremented

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

        # Fixup any references to this one.
        for gen_literal in branch.gen_literals:
            assert self.branchmap[gen_literal] is branch
            self.branchmap[gen_literal] = other

    def iter_branch_todo_away(self, branch):
        """
        Exhausts a todo set of literals of the given branch, yielding them
        among with corresponding branches.

        Yields: (literal, branch) tuples. Neither literals included in the
        branch nor in self are yielded (they are simply discarded from the
        todo set).
        Note: The iterator is modification-safe.
        """
        if self is not branch.trunk:
            raise ValueError("Branch must be created from this trunk")

        for literal in branch.iter_todo_away():
            try:
                implied = self.branchmap[literal]

            except KeyError:
                assert ~literal in self.literals
                # If ~literal was added by create_trunk, then there is
                # no branch for literal, even dead. In this case yield None.
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

        self.trunk   = trunk
        self.baserev = trunk.rev  # always 0 as long as all branches are
                                  # created before any commit to trunk

        self.todo = set()  # literals
        self.negexcls = defaultdict(set)  # {neglast: literals...}

    def dispose(self):
        self.trunk = None
        del self.todo
        del self.negexcls
        super(Diff, self).dispose()

    def flatten(self):
        if not self.ready:
            raise ValueError('not ready: {0}: {0.todo}'.format(self))

        trunk = self.trunk
        if self.baserev == trunk.rev:
            changesets = [trunk]
        else:
            changesets = [trunk.base] + trunk.commits[:self.baserev]
        changesets.append(self)

        ret = Solution()
        for diff in changesets:
            assert ret.isdisjoint(diff)
            ret |= diff

        return ret

    def _check_capable(self, other):
        if self.trunk is not other.trunk:
            raise ValueError('Both diffs must belong to the same trunk')
        if not other.ready:
            raise ValueError('not ready: {0}: {0.todo}'.format(other))

    def merge(self, other):
        self._check_capable(other)

        for neglast, negexcl in iteritems(other.negexcls):
            assert self.trunk.neglefts[neglast] >= negexcl
            self.__do_neglast(neglast, operator.__ior__, negexcl)

        self |= other

    def reverse_merge(self, other):
        self._check_capable(other)

        for neglast, negexcl in iteritems(other.negexcls):
            self.__do_neglast(neglast, operator.__isub__, negexcl)

        self -= other

    def add_literal(self, literal, add_node=True):
        for neglast in literal.neglasts:
            self.__do_neglast(neglast, invoker.add(literal))

        if literal not in self.trunk.literals:
            self.literals.add(literal)
        if add_node and literal.node not in self.trunk.nodes:
            self.nodes.add(literal.node)

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

            if neg_reason not in self.trunk.reasons:
                self.reasons.add(neg_reason)
            self.todo.add(neg_literal)

    def iter_todo_away(self):
        literals = self.literals
        trunk_literals = self.trunk.literals
        return (literal for literal in pop_iter(self.todo)
                if (literal not in literals and
                    literal not in trunk_literals))

    def __repr__(self):
        return ('<{cls.__name__} ({state}/{nr_todos})>'
                .format(cls=type(self),
                        nr_todos=len(self.todo),
                        state='valid' if self.valid else 'dead'))


class Branch(Diff):
    """docstring for Branch"""

    _dump_attrs = (Diff._dump_attrs + 'gen_literals'.split())

    def __init__(self, trunk, gen_literal):
        super(Branch, self).__init__(trunk)
        self.gen_literals = set()

        self.gen_literals.add(gen_literal)
        self.add_literal(gen_literal)

        self.todo |= gen_literal.implies

    def merge(self, other):
        if self.literals >= other.gen_literals:  # other is already in self
            assert self.nodes    >= other.nodes
            assert self.literals >= other.literals
            assert self.reasons  >= other.reasons
            assert self.todo     >= other.todo
            assert all(self.negexcls[neglast] >= negexcl
                       for neglast, negexcl in iteritems(other.negexcls))
            return

        super(Branch, self).merge(other)

    def __repr__(self):
        try:
            return ('<{cls.__name__} ({state}/{nr_todos}) {gen_list!r}>'
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
        reasons.add(Reason(literal))

    literals |= todo

    for literal in pop_iter(todo):
        logger.debug('\ttrunk literal: %r', literal)

        assert literal in literals, "must has already been added"
        nodes.add(literal.node)

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

        raise SolveError(trunk)

    logger.info('created trunk with %d node(s)', len(trunk.nodes))

    unresolved_nodes = (pgraph.nodes - trunk.nodes)
    logger.info('preparing branchmap for %d unresolved node(s)',
                len(unresolved_nodes))

    for node in unresolved_nodes:
        logger.debug('\tunresolved node: %r', node)

        for literal in node:
            trunk.branchmap[literal] = Branch(trunk, literal)

    assert len(trunk.branchmap) == 2*len(unresolved_nodes)

    logger.dump(trunk)
    return trunk


def expand_branch(branch):
    """Handles all branch todos (if any), in other words makes it ready.

    Implementation of non-recursive DFS."""
    if branch.ready:
        return

    trunk = branch.trunk

    stack = list()

    def stack_push(branch):
        assert not hasattr(branch, 'todo_it'), ("A branch has 'todo_it' attr "
                                                "iff it is already in stack")
        branch.todo_it = trunk.iter_branch_todo_away(branch)
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
            logger.debug('\t%s todo literal: %r, implied: %r', log_indent,
                         literal, implied)

            if hasattr(implied, 'todo_it'):  # equivalent (mutual implication)
                logger.debug('\t%s(mutual implication with %r)', log_indent,
                             implied)
                implied.todo |= branch.todo
                branch.todo.clear()  # otherwise merge() would refuse it

                implied.merge(branch)

                trunk.substitute_branch(branch, implied)
                branch.dispose()  # forget about this branch and make gc happy
                raise StopIteration

        except StopIteration:
            logger.debug('\t%ssucceeded %r', log_indent, branch)
            stack_pop()

        else:
            if implied is None or not implied.valid:
                logger.debug('\t%s(implied is not valid: %r)', log_indent,
                             implied)
                branch.add_literal(literal, add_node=False)
                if implied is not None:
                    branch.reasons.add(Reason(None, [literal], 
                                              why=why_implies_dead_branch,
                                              follow=True))

            elif implied.ready:
                branch.merge(implied)

            else:
                logger.debug('\t%sdeferred  %r', log_indent, branch)
                # The best thing we can do here is to put the literal back
                # into todo set to restart handling it later with properly
                # initialized (and possibly substituted) implied branch.
                branch.todo.add(literal)

                stack_push(implied) # what to handle next


def expand_branchset(trunk):
    branchset = trunk.branchset() | set(itervalues(trunk.dead_branches))

    for branch in filter(getter.trunked, branchset):
        expand_branch(branch)


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
   
    why = why_default
    follow = False
    
    if branches is None:
        branches = branchset_to_resolve(trunk)
        why=why_implied_by_dead_branch
        follow = True

    while branches:
        logger.info('resolving %d branch(es)', len(branches))
        logger.dump(trunk)

        resolved = Diff(trunk)  # created by merging together all diffs

        for branch in branches:
            logger.debug('\t+merge %r', branch)
            for gen_literal in branch.gen_literals:
                resolved.reasons.add(Reason(gen_literal, why=why, 
                                            follow=follow))

            resolved.merge(branch)
        expand_branch(resolved)  # handle todos, if any

        logger.dump(resolved)
        if not resolved.valid:
            logger.info('resolved is not valid, giving up')
            #TODO chek this commit works correctly
            trunk.commit(resolved)
            raise SolveError(trunk)

        # Reintegrate into trunk. This also removes resolved branches and
        # their opposites (refused branches) from branchmap.
        trunk.commit(resolved)

        # Maintain remaining branches to be strict diffs with just updated
        # trunk. This may involve new conflicts, i.e. new branches can be
        # resolved next.
        for branch in trunk.branchset():
            logger.debug('\t-merge %r', branch)
            branch.reverse_merge(resolved)
        expand_branchset(trunk)

        branches = branchset_to_resolve(trunk)

    logger.dump(trunk)


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

    return trunk


def solve(pgraph, initial_values={}):
    from mybuild.rgraph import *
    logger.info('solving %r with initials: %r', pgraph, initial_values)

    trunk = solve_trunk(pgraph, initial_values)
    #TODO will be removed, just for preliminary test
#     rgraph = get_rgraph(trunk)
#     rgraph.print_graph()
    ret = dict.fromkeys(pgraph.nodes)
    ret.update(trunk.literals)
    logger.debug('Solution:')
    for literal in ret:
        logger.debug('\t%s: %s', literal, ret[literal])
    return ret
           
def why_implied_by_dead_branch(literal, *cause_literals):
    return '%s because of dead branch %s' % (literal, ~literal)

def why_implies_dead_branch(literal, *cause_literals):
    return '%s implies dead branch' % (literal)

def why_default(literal, *cause_literals):
    return '%s by default' % (literal)  

class SolveError(Exception):
    """docstring for SolveError"""
    
    def __init__(self, trunk):
        super(SolveError, self).__init__()
        self.trunk = trunk
