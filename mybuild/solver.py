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


class Context(object):
    """
    Context backed by sets of nodes and their literals.
    """

    @property
    def valid(self):
        return len(self.nodes) == len(self.literals)

    @property
    def cost(self):
        return sum(literal.cost for literal in self.literals)

    def __init__(self):
        super(Context, self).__init__()

        self.nodes    = set()
        self.literals = set()
        self.reasons  = set()

    def __len__(self):
        return len(self.literals)

    def __repr__(self):
        return ' & '.join(repr(literal).join('()')
                          for literal in self.literals)

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

    def clear(self):
        self.nodes.clear()
        self.literals.clear()
        self.reasons.clear()

    def update(self, other, check=False):
        if check and not other.valid:
            raise ContextError(self)

        self |= other

        if check and not self.valid:
            raise ContextError(self)

    def difference_update(self, other, check=False):
        if check and not other.valid:
            raise ContextError(self)

        self -= other

        if check and not self.valid:
            raise ContextError(self)

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

    def __ior__(self, branch):
        if self is not branch.trunk:
            raise ValueError('Branch must belong to this trunk')

        for neglast, negexcl in iteritems(branch.negexcls):
            self.neglefts[neglast] -= negexcl

        return super(TrunkContext, self).__ior__(branch)

    def __isub__(self, other):
        return NotImplemented


class BranchContextBase(Context):
    """docstring for BranchContextBase"""

    def __init__(self, trunk):
        super(BranchContextBase, self).__init__()

        self.trunk        = trunk
        self.gen_literals = set()

        self.negexcls   = defaultdict(set)
        self.todo       = set()

    def __ior__(self, other):
        if self.trunk is not other.trunk:
            raise ValueError('Both branches must belong to the same trunk')

        if self.literals >= other.gen_literals:
            assert self.nodes    >= other.nodes
            assert self.literals >= other.literals
            assert self.reasons  >= other.reasons
            assert self.todo     >= other.todo
            for neglast, negexcl in iteritems(other.negexcls):
                assert self.negexcls[neglast] >= negexcl
            return self

        self.todo |= other.todo

        for neglast, negexcl in iteritems(other.negexcls):
            self.__do_neglast(neglast, operator.__ior__, negexcl)

        return super(BranchContextBase, self).__ior__(other)

    def __isub__(self, other):
        if self.trunk is not other.trunk:
            raise ValueError('Both branches must belong to the same trunk')
        if other.todo:
            raise NotImplementedError('Other is not ready')

        for neglast, negexcl in iteritems(other.negexcls):
            self.__do_neglast(neglast, operator.__isub__, negexcl)

        return super(BranchContextBase, self).__isub__(other)

    def clear(self):
        self.negexcls.clear()
        self.todo.clear()
        super(BranchContextBase, self).clear()

    def add_literal(self, literal, reason=None):
        for neglast in literal.neglasts:
            self.__do_neglast(neglast, operator.methodcaller('add', literal))

        super(BranchContextBase, self).add_literal(literal, reason)

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

class BranchContext(BranchContextBase):
    """docstring for BranchContext"""

    @property
    def valid(self):
        return self.error is None and len(self.nodes) == len(self.literals)

    @property
    def initialized(self):
        return bool(self.literals)

    def __init__(self, trunk, *gen_literals):
        super(BranchContext, self).__init__(trunk)

        self.gen_literals.update(gen_literals)

        self.implicants = set()
        self.init_task  = None
        self.error      = None


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
            implied = next(stack[-1].init_task)

        except StopIteration:
            # print ' .' * len(stack), 'branch %r done' % (id(stack[-1]) % 37)
            stack.pop().init_task = None

        except ContextError as error:
            # print ' .' * len(stack), 'branch %r dies' % (id(stack[-1]) % 37)
            # unwind implication stack
            for implicant in reversed(stack):
                implicant.init_task = None
                implicant.error = error
                error = ContextError(implicant, error)
            raise

        else:
            assert not implied.initialized and implied.init_task is None

            implied.init_task = branch_init_task(implied)
            stack.append(implied)


def iter_todo(branch):
    trunk = branch.trunk

    for literal in pop_iter(branch.todo):
        if literal in branch.literals:
            continue  # already handled

        try:
            implied = trunk.branchmap[literal]

        except KeyError:
            if literal in trunk.literals:
                continue  # included in the trunk, i.e. unconditionally

            assert ~literal in trunk.literals
            raise ContextError(branch)

        yield literal, implied


def branch_init_task(branch):
    trunk = branch.trunk

    for gen_literal in branch.gen_literals:
        branch.add_literal(gen_literal)

        branch.reasons.update(gen_literal.imply_reasons)
        branch.todo |= gen_literal.implies

    for literal, implied in iter_todo(branch):
        # print ' ' * 60, id(branch) % 37, '->', id(implied) % 37, '\t', literal

        if implied.init_task is not None:
            # Equivalent (mutual implication), swap branches.
            implied.gen_literals |= branch.gen_literals

            # Fixup any references to an old branch.
            for gen_literal in branch.gen_literals:
                trunk.branchmap[gen_literal] = implied

            implied.update(branch, check=True)
            break  # forget about this branch, nothing more to do here

        elif implied.initialized:
            implied.implicants.add(branch)
            implied.implicants |= branch.implicants

            branch.update(implied, check=True)

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
            branch.todo.add(literal)


def prepare_branches(trunk, unresolved_nodes):
    for node in unresolved_nodes:
        for literal in node:
            trunk.branchmap[literal] = BranchContext(trunk, literal)

    assert len(trunk.branchmap) == 2*len(unresolved_nodes)


def resolve_branches(trunk):
    resolved = BranchContextBase(trunk)

    for literal, branch in iteritems(trunk.branchmap):
        try:
            initialize_branch(branch)
        except ContextError:
            assert not branch.valid
        if not branch.valid:
            resolved.todo.add(~literal)  # TODO reason

    while resolved.todo:
        for literal, branch in iter_todo(resolved):
            resolved.update(branch, check=True)

        trunk.update(resolved, check=True)

        for literal in resolved.literals:
            for each in literal.node:  # remove both literal and ~literal
                del trunk.branchmap[each]

        resolved.clear()

        for literal, branch in iteritems(trunk.branchmap):
            if not branch.valid:
                continue
            try:
                branch.difference_update(resolved, check=True)
            except ContextError:
                resolved.todo.add(~literal)  # TODO reason


def combine_branches(trunk):
    branches = sorted(set(itervalues(trunk.branchmap)),
                      key=operator.attrgetter('cost'))
    assert all(branch.valid for branch in branches)

    print [('%r: %d' % (branch, branch.cost)) for branch in branches]


def solve(pgraph, initial_values):
    nodes = pgraph.nodes

    trunk = create_trunk(pgraph, initial_values)
    # for literal in trunk.literals:
    #     print 'trunk', literal

    prepare_branches(trunk, nodes-trunk.nodes)
    resolve_branches(trunk)
    combine_branches(trunk)

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

