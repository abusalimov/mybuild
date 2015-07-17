"""
Graph for reasons of pgraph solution
"""
from __future__ import absolute_import, division, print_function
from mybuild._compat import *

import heapq
import logging
from collections import deque

from mybuild.req.pgraph import Reason


__author__ = "Vita Loginova"
__date__ = "2013-06-28"


logger = logging.getLogger(__name__)


class Rnode(object):
    def __init__(self, literal, rgraph):
        super(Rnode, self).__init__()

        self.rgraph = rgraph
        self.literal = literal

        self.containers = set()
        self.becauseof = {} # key = Container, value = Reason

        self.length = float("+inf")
        self.parent = None

    def __repr__(self):
        return ("<{cls.__name__}: {literal}>"
                .format(cls=type(self), literal=self.literal))

    def container(self):
        return self.rgraph.containers[frozenset([self.literal])]

class Container(object):
    @property
    def length(self):
        return sum(member.length for member in self.members)

    def __init__(self, literals, rgraph):
        super(Container, self).__init__()

        self.rgraph = rgraph

        self.literals = frozenset(literals)
        self.members = set()
        self.therefore = {} # key = Rnode, value = Reason

    def __repr__(self):
        return ("<{cls.__name__}: {literals}>"
                .format(cls=type(self), literals=list(self.literals)))

    def update(self):
        for literal in self.literals:
            member = self.rgraph.nodes[literal]
            self.members.add(member)
            member.containers.add(self)


class Rgraph(object):
    """
    Rgraph or Reason graph
    """
    def __init__(self, solution):
        self.initial = Container(set(), self)

        self.containers = {}
        self.containers[frozenset()] = self.initial
        self.containers[frozenset([None])] = self.initial

        self.nodes = {}
        self.violation_graphs = {}

        # logger.dump(solution)

        for node in solution.nodes:
            for literal in node:
                self.nodes[literal] = Rnode(literal, self)

                literal_set = frozenset([literal])
                self.containers[literal_set] = Container(literal_set, self)

        for reason in solution.reasons:
            self.initialize_nodes(reason)

        for literal in solution.literals:
            for reason in literal.imply_reasons:
                self.initialize_nodes(reason)

        for literals, container in iteritems(self.containers):
            container.update()

        self.find_shortest_paths()

    def initialize_nodes(self, reason):
        cause_literals = frozenset(reason.cause_literals)
        if cause_literals not in self.containers:
            self.containers[cause_literals] = Container(cause_literals, self)

        literal_node = self.nodes[reason.literal]
        cause_container = self.containers[cause_literals]

        literal_node.becauseof[cause_container] = reason
        cause_container.therefore[literal_node] = reason

    def find_shortest_paths(self):
        """
        Finds the shortest paths to each of the self.nodes using modified
        Dijkstra's algorithm. The length of path to node is computed as
        a sum of it's becauseof.
        Output:
            Rnode.length - length of the shortest path (inf if there is no one)
            Rnode.parent - cause container (self for initials and None for ones
                                            with infinite length)
        """
        queue = []
        used = set()

        def update_and_post(node, parent):
            length = 0 if node == parent else parent.length + 1
            node.length = length
            node.parent = parent
            for container in node.containers:
                heapq.heappush(queue, (container.length, container))

        heapq.heapify(queue)

        for container in self.initial.therefore:
            update_and_post(container, container)

        while queue:
            length, container = heapq.heappop(queue)

            if container in used:
                continue
            used.add(container)

            for cons in container.therefore:
                if cons.length > length + 1:
                    update_and_post(cons, container)

        logger.debug('Lengths for shortest ways to {0}'.format(self))
        for node in itervalues(self.nodes):
            logger.debug('{0}: length {1}'.format(node, node.length))

    def make_bare_copy(self):
        """
        Returns rgraph with same nodes but without any reason
        """
        cls = type(self)
        new = cls.__new__(cls)

        new.nodes = {}
        new.containers = {}
        new.violation_graphs = {}

        for literal, node in iteritems(self.nodes):
            new.nodes[literal] = Rnode(literal, new)

        for literals, container in iteritems(self.containers):
            new.containers[literals] = Container(container.literals, new)
            new.containers[literals].update()

        new.initial = new.containers[frozenset()]

        return new


def shorten_rgraph(rgraph, rnodes):
    """
    Constructs rgraph containing the the most shortest paths to the rnodes
    passed as argument.
    """
    def set_path(rgraph_copy, container):
        for member in container.members:
            if member.length == 0:
                rgraph_copy.initialize_nodes(member.becauseof[rgraph.initial])
            else:
                set_path(rgraph_copy, member.parent)
                rgraph_copy.initialize_nodes(member.becauseof[member.parent])

    rgraph_copy = rgraph.make_bare_copy()
    for node in rnodes:
        if node.length == float("+inf"):
            raise Exception('No way to {0}'.format(node))
        set_path(rgraph_copy, node.container())

    return rgraph_copy


def shorten_error_rgraph(rgraph, violation_nodes):
    """
    Constructs rgraph containing only the most shortest paths to violation
    nodes with smallest length.
    """
    def length(node):
        return sum(rgraph.nodes[literal].length for literal in node)

    min_length = length(min(violation_nodes, key = length))

    nodes = filter(lambda node: min_length == length(node), violation_nodes)

    rnodes = set()
    for node in nodes:
        rnodes.add(rgraph.nodes[node[False]])
        rnodes.add(rgraph.nodes[node[True]])

    if rnodes:
        return shorten_rgraph(rgraph, rnodes)

    return shorten_rgraph(rgraph, [rgraph.initial])


def prepare_rgraph_branch(trunk, branch):
    solution = branch.flatten()
    # TODO move to solver
    for gen_literal in branch.gen_literals:
        solution.reasons.add(Reason(gen_literal))

    for literal in solution.literals:
        for reason in literal.imply_reasons[:]:
            if (literal in trunk.dead_branches and
                literal not in branch.gen_literals):
                literal.imply_reasons.remove(reason)

    return solution


def get_violation_nodes(solution):
    def is_violation(node):
        literals = solution.literals
        return node[False] in literals and node[True] in literals

    return filter(is_violation, solution.nodes)


def get_error_rgraph(solution, is_short=True):
    def build_rgraph(branch):
        rgraph = Rgraph(branch)
        if is_short:
            violation_nodes = list(get_violation_nodes(branch))
            rgraph = shorten_error_rgraph(rgraph, violation_nodes)
        return rgraph

    trunk = solution.trunk
    rgraph = build_rgraph(trunk)

    branchmap = {}
    for literal, branch in iteritems(trunk.dead_branches):
        if branch.valid:
            continue

        if frozenset(branch.gen_literals) in branchmap:
            rgraph_branch = branchmap[frozenset(branch.gen_literals)]
            rgraph.violation_graphs[literal] = rgraph_branch
            continue

        branch_solution = prepare_rgraph_branch(trunk, branch)
        rgraph_branch = build_rgraph(branch_solution)
        rgraph_branch.violation_graphs = rgraph.violation_graphs

        branchmap[frozenset(branch.gen_literals)] = rgraph_branch
        rgraph.violation_graphs[literal] = rgraph_branch

    return rgraph


def traverse_error_rgraph(rgraph):
    """
    Traverses the input rgraph and yields tuples (reason, shift) in the reverse
    order. The reverse order is chosen in order to make output examination more
    natural to users.

    In case input rgraph is shortened, the outermost level (shift is 0) helps to
    answer WHICH module led to the violation, the rest ones tell HOW the
    solver got this.

    In case the rgraph is full, the outermost reasons may correspond
    an alternative path to some node. So that this method is most useful in
    case of shortened rgraph.

    Examine the example:

        Input:
        A -> B
            B -> C
                C -> D
            B -> D

        Output:
        D <- C
            C <- B
                B <- A
        B <- D

    Yields:
        (reason, shift) pairs
    """
    node_deque = deque()
    visited_nodes = set()
    visited_containers = set()
    reason_list = []

    def dfs(node, reason):
        is_visited = node in visited_nodes
        container = node.container()

        if not is_visited:
            visited_nodes.add(node)
            visited_containers.add(container)
            reason_list.append(reason)

        if is_visited or not container.therefore:
            yield reason_list[:]
            reason_list[:] = []
            return

        for cons, reason in iteritems(container.therefore):
            for each in dfs(cons, reason):
                yield each
            for cons_container in cons.containers:
                post_traversal(cons_container)

    def post_traversal(container):
        if container in visited_containers:
            return

        visited_containers.add(container)

        for cons, reason in iteritems(container.therefore):
            if cons not in node_deque and cons not in visited_nodes:
                node_deque.appendleft((cons, reason))

    for node, reason in iteritems(rgraph.initial.therefore):
        node_deque.append((node, reason))
        post_traversal(node.container())

    while node_deque:
        node, reason = node_deque.pop()
        for chain in dfs(node, reason):
            shift = 0
            while chain:
                yield chain.pop(), shift
                shift += 1
