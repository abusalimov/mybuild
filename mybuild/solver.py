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

import logs as log


class Context(namedtuple('_Context', 'nodes, literals, reasons')):
    """
    Context backed by sets of nodes and their literals.
    """

    @property
    def valid(self):
        return len(self.nodes) == len(self.literals)

    def __new__(cls, *args, **kwargs):
        return super(Context, cls).__new__(cls,
            nodes    = set(),
            literals = set(),
            reasons  = set())

    def __len__(self):
        return len(self.literals)

    def __ior__(self, other):
        for s, o in zip(self, other):
            s |= o
        return self

    def __isub__(self, other):
        for s, o in zip(self, other):
            s -= o
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

    def branch_for(self, literal):
        """
        Returns branch, which effectively is an implication closure of given
        literal.
        """

        if literal in self.literals:
            return None

        if literal.node in self.nodes:
            raise ContextError(self)

        try:
            branch = self.branchmap[literal]
        except KeyError:
            branch = self.branchmap[literal] = BranchContext(literal)

        return branch


class BranchContext(Context):
    """docstring for BranchContext"""

    @property
    def valid(self):
        return self.error is None and len(self.nodes) == len(self.literals)

    @property
    def fresh(self):
        return not self.literals

    def __init__(self, gen_literal):
        super(BranchContext, self).__init__()

        self.gen_literals = set([gen_literal])

        self.implicants = set()
        self.negexcls = defaultdict(set)
        self.init_task = None
        self.error = None


def create_trunk(pgraph, initial_literals=[]):
    (nodes, literals, reasons) = trunk = TrunkContext()
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


def initialize_branch(trunk, branch):
    """
    Merges all implied branches into the given one.

    Upon returning the branch is completely initialized, unless a ContextError
    has been raised. In the latter case the branch is considered invalid (not
    branch.valid) and the raised error is remembered in branch.error attribute.
    """
    assert branch.init_task is None

    if not branch.fresh:
        return

    branch.init_task = branch_init_task(trunk, branch)
    stack = [branch]

    while stack:
        try:
            # print ' .' * len(stack), 'branch %r for:' % \
            #   (id(stack[-1]) % 37), sorted(stack[-1].gen_literals)

            implied = stack[-1].init_task.next()
            if isinstance(implied, ContextError):
                raise implied

            # print ' .' * len(stack), ' (defer until %r: %r)' % \
            #   (id(implied) % 37, tuple(implied.gen_literals)[0])
        except StopIteration:
            stack.pop().init_task = None

        except ContextError as error:
            # unwind branch stack
            for implicant in reversed(stack):
                implicant.error = error
                error = ContextError(implicant, error)
            raise

        else:
            assert implied.fresh and implied.init_task is None

            implied.init_task = branch_init_task(trunk, implied)
            stack.append(implied)


def branch_init_task(trunk, branch):
    init_literal, = branch.gen_literals  # assumed to be singular

    branch.add_literal(init_literal)

    # TODO add a Reason for init_literal (not here)
    branch.reasons.update(init_literal.imply_reasons)

    todo = set(init_literal.implies)
    while todo:
        literal = todo.pop()
        if literal in branch.literals:
            continue  # already handled

        try:
            implied = trunk.branch_for(literal)
            if implied is None:
                continue  # included in the trunk, i.e. unconditionally

            if implied.fresh:
                yield implied  # defer until a branch is initialized

            if literal in branch.gen_literals:
                continue  # branches have been swapped

            assert literal in implied.gen_literals

            if not implied.valid:
                raise ContextError(branch)

            if implied.init_task is None:
                implied.implicants |= branch.gen_literals

            else:  # equivalent (mutual implication)
                # Forget about this branch, switch to the implicant one.
                branch, implied = swap_branches(trunk, branch, implied)

            imply_branch(trunk, branch, implied, todo)

        except ContextError as e:
            yield e


def swap_branches(trunk, branch, other):
    # Fixup any references to an old branch.
    for gen_literal in branch.gen_literals:
        assert trunk.branchmap[gen_literal] is branch
        trunk.branchmap[gen_literal] = other

    other.gen_literals |= branch.gen_literals

    return other, branch


def imply_branch(trunk, branch, other, todo):
    branch |= other

    for neglast, other_negexcl in iteritems(other.negexcls):
        negleft = trunk.neglefts[neglast]

        negexcl = branch.negexcls[neglast]
        negexcl |= other_negexcl

        left = len(negleft) - len(negexcl)
        if left > 1:
            continue

        neg_literal, neg_reason = neglast.neg_reason_for(
            last_literal=(negleft-negexcl).pop() if left else None)

        branch.reasons.add(neg_reason)
        todo.add(neg_literal)

    if not branch.valid:
        raise ContextError(branch)


def merge_into_trunk(trunk, branch):
    trunk |= branch

    assert branch.valid and trunk.valid

    for neglast, negexcl in iteritems(branch.negexcls):
        trunk.neglefts[neglast] -= negexcl

    neg_lset = set(map(operator.__invert__, branch.literals))

    for other in map(trunk.branchmap.get, branch.implicants):
        if not other.valid:
            continue



def revert_changes(trunk, branch, other):
    pass


def create_branch(trunk, literal):
    branch = trunk.branch_for(literal)

    try:
        initialize_branch(trunk, branch)
    except ContextError:
        assert not branch.valid

    return branch


def n_valid(pair):
    return sum(branch.valid for branch in pair)
def single_valid(pair):
    if n_valid(pair) == 1:
        return pair[pair[True].valid]

def prepare_branches(trunk, unresolved_nodes):
    if not unresolved_nodes:
        return

    for node in unresolved_nodes:
        for literal in node:
            create_branch(trunk, literal)

    assert len(trunk.branchmap) == 2*len(unresolved_nodes)

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

