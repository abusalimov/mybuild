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
from collections import namedtuple
from itertools import izip
from itertools import repeat
import operator

from compat import *
from pgraph import *

from util import bools
from util import filter_bypass
from util import map_bypass
from util import pop_iter
from util import send_next_iter

import logs as log


class Context(object):
    """
    Context backed by sets of nodes and their literals.
    """

    @property
    def valid(self):
        return len(self.nodes) == len(self.literals)

    def __init__(self):
        super(Context, self).__init__()

        self.nodes    = set()
        self.literals = set()
        self.reasons  = set()

    def __len__(self):
        return len(self.literals)

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

    def add_literal(self, literal, reason=None):
        self.literals.add(literal)
        self.nodes.add(literal.node)
        if reason is not None:
            self.reasons.add(reason)


class TrunkContext(Context):
    """docstring for TrunkContext"""

    def __init__(self):
        super(TrunkContext, self).__init__()

        self.branchmap = dict()  # maps gen literals to branches
        self.neglefts = dict()   # neglasts to sets of left literals


class BranchContext(Context):
    """docstring for BranchContext"""

    @property
    def valid(self):
        return self.error is None and len(self.nodes) == len(self.literals)

    @property
    def initialized(self):
        return bool(self.literals)

    def __init__(self, trunk, *gen_literals):
        super(BranchContext, self).__init__()

        self.trunk        = trunk
        self.gen_literals = set(gen_literals)

        self.negexcls   = defaultdict(set)
        self.todo       = set()

        self.implicants = set()
        self.init_task  = None
        self.error      = None

    def __ior__(self, other):
        trunk = self.trunk
        if trunk is not other.trunk:
            raise ValueError('Both branches must belong to the same trunk')

        for neglast, other_negexcl in iteritems(other.negexcls):
            negexcl = self.negexcls[neglast]
            negexcl |= other_negexcl

            self.__check_neglast(neglast, negexcl)

        self.todo |= other.todo

        return super(BranchContext, self).__ior__(other)

    def add_literal(self, literal, reason=None):
        for neglast in literal.neglasts:
            negexcl = self.negexcls[neglast]
            negexcl.add(literal)

            self.__check_neglast(neglast, negexcl)

        super(BranchContext, self).add_literal(literal, reason)

    def __check_neglast(self, neglast, negexcl):
        negleft = self.trunk.neglefts[neglast]

        left = len(negleft) - len(negexcl)
        if left <= 1:
            neg_literal, neg_reason = neglast.neg_reason_for(
                last_literal=(negleft-negexcl).pop() if left else None)

            self.reasons.add(neg_reason)
            self.todo.add(neg_literal)


def create_trunk(pgraph, initial_literals=[]):
    trunk = TrunkContext()

    nodes    = trunk.nodes
    literals = trunk.literals
    reasons  = trunk.reasons
    neglefts = trunk.neglefts

    neglasts_todo = list()

    for node in pgraph.nodes:
        for literal in node:
            for neglast in literal.neglasts:
                negleft = neglefts[neglast] = set(neglast.literals)

                if len(negleft) <= 1:  # should not happen, generally speaking
                    neglasts_todo.append(neglast)

    # During the loop below we admit possible violation of the main context
    # invariant, i.e. len(nodes) may become less than len(literals).
    #
    # A difference between implication closures of conflicting literals is
    # accumulated in order to be able to produce better error reporting
    # because of keeping more reason chains for all literals.
    todo = to_lset(initial_literals)
    todo.update(pgraph.const_literals)

    literals |= todo

    while todo:
        literal = todo.pop()

        assert literal in literals, "must has already been added"
        nodes.add(literal.node)

        reasons.update(literal.imply_reasons)

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
        raise ContextError(trunk)

    return trunk


def initialize_branch(branch):
    """
    Merges all implied branches into the given one.

    Upon returning the branch is completely initialized, unless a ContextError
    has been raised. In the latter case the branch is considered invalid (not
    branch.valid) and the raised error is remembered in branch.error attribute.
    """
    assert branch.init_task is None

    if branch.initialized:
        return

    branch.init_task = branch_init_task(branch)
    stack = [branch]

    while stack:
        try:
            # print ' .' * len(stack), 'branch %r for:' % \
            #   (id(stack[-1]) % 37), sorted(stack[-1].gen_literals)
            implied = stack[-1].init_task.next()

        except StopIteration:
            stack.pop().init_task = None

        except ContextError as error:
            # unwind branch stack
            for implicant in reversed(stack):
                implicant.init_task = None
                implicant.error = error
                error = ContextError(implicant, error)
            raise

        else:
            assert not implied.initialized and implied.init_task is None

            implied.init_task = branch_init_task(implied)
            stack.append(implied)


def branch_init_task(branch):
    trunk = branch.trunk

    for gen_literal in branch.gen_literals:
        branch.add_literal(gen_literal)

        branch.reasons.update(gen_literal.imply_reasons)
        branch.todo |= gen_literal.implies

    todo_it = send_next_iter(pop_iter(branch.todo))

    for literal in todo_it:
        if literal in branch.literals:
            continue  # already handled

        try:
            implied = trunk.branchmap[literal]

        except KeyError:
            if literal in trunk.literals:
                continue  # included in the trunk, i.e. unconditionally

            assert ~literal in trunk.literals
            raise ContextError(branch)

        if implied.init_task is not None:
            # Equivalent (mutual implication), swap branches.
            implied.gen_literals |= branch.gen_literals

            # Fixup any references to an old branch.
            for gen_literal in branch.gen_literals:
                trunk.branchmap[gen_literal] = implied

            imply_branch(implied, branch)
            break  # forget about this branch, nothing more to do here

        elif implied.initialized:
            implied.implicants.add(branch)
            implied.implicants |= branch.implicants

            imply_branch(branch, implied)

        else:
            yield implied  # defer until a branch is initialized

            # During initialization of the implied branch it may have been
            # swapped with an implicant (appears upper on the stack).
            #
            # Example:
            #   A => B => C => A
            #           ^- assuming we're handling this implication now
            #
            # Upon returning back from 'yield' above, a branch initially
            # created for C gets swapped with A and should not be used
            # anymore.
            #
            # So the best thing we can do here is to restart handling the
            # literal from the beginning.
            todo_it.send(literal)


def imply_branch(branch, implied):
    if not implied.valid:
        raise ContextError(branch)

    branch |= implied

    if not branch.valid:
        raise ContextError(branch)


def merge_into_trunk(trunk, branch):
    trunk |= branch

    assert branch.valid and trunk.valid

    for neglast, negexcl in iteritems(branch.negexcls):
        trunk.neglefts[neglast] -= negexcl

    neg_lset = set(map(operator.__invert__, branch.literals))

    for other in branch.implicants:
        if not other.valid:
            continue


def revert_changes(trunk, branch, other):
    pass


def n_valid(pair):
    return sum(bool(branch.valid) for branch in pair)

def single_valid(pair):
    if n_valid(pair) == 1:
        return pair[pair[True].valid]


def prepare_branches(trunk, unresolved_nodes):
    if not unresolved_nodes:
        return

    for node in unresolved_nodes:
        for literal in node:
            trunk.branchmap[literal] = BranchContext(trunk, literal)

    assert len(trunk.branchmap) == 2*len(unresolved_nodes)

    for branch in itervalues(trunk.branchmap):
        try:
            initialize_branch(branch)
        except ContextError:
            assert not branch.valid

    branch_pairs = list(node._map_with(trunk.branchmap.get)
                        for node in unresolved_nodes)
    branch_pairs.sort(key=n_valid)

    for pair in branch_pairs:
        if not n_valid(pair):
            raise ContextError

        branch = single_valid(pair)
        if branch is None:
            continue

        merge_into_trunk(trunk, branch)


def solve(pgraph, initial_values):
    nodes = pgraph.nodes

    trunk = create_trunk(pgraph, initial_values)

    prepare_branches(trunk, nodes-trunk.nodes)

    ret = dict.fromkeys(nodes)
    ret.update(trunk.literals)
    return ret


class SolveError(Exception):
    """docstring for SolveError"""

class ContextError(SolveError):
    """docstring for ContextError"""

    def __init__(self, context, cause=None):
        super(ContextError, self).__init__()
        self.context = context
        self.cause = cause

