"""
Graph for reasons of pgraph solution
"""

__author__ = "Vita Loginova"
__date__ = "2013-06-28"


from  _compat import *

import heapq
from collections import deque

from mybuild.pgraph import Reason

from util.operator import getter
from util.operator import invoker

import util, logging
logger = util.get_extended_logger(__name__)


class NodeContainer(object):

    @property
    def length(self):
        if self.members:
            return sum(r.length for r in self.members)
        else:
            return self._length

    @length.setter
    def length(self, value):
        self._length = value

    def __init__(self, literals):
        self.literals = frozenset(literals)
        self.containers = set() #NodeContainrs set that contains nodes with
                                #current node as member
        self.members = set()    #Node set of nodes with one literal from
                                #node.literals
        self.therefore = {} #key = node, value = reason
        self.becauseof = {} #key = node, value = reason
        self._length = float("+inf")
        self.parent = None

    def __lt__(self, other):
        return self.length < other.length

    def compare_literals(self, literals):
        return (set(literals) == self.literals)

    def __repr__(self):
        return ("<{cls.__name__}: {literals}>"
                .format(cls=type(self), literals=list(self.literals)))


class Rgraph(object):
    """
    Rgraph or Reason graph
    """
    def __init__(self, solution):
        self.initial = NodeContainer(set())
        self.nodes = {}
        self.nodes[frozenset()] = self.initial
        self.nodes[frozenset([None])] = self.initial
        self.violation_graphs = {}

        logger.dump(solution)

        for literal in solution.literals:
            self.nodes[frozenset([literal])] = NodeContainer(frozenset([literal]))
            self.nodes[frozenset([~literal])] = NodeContainer(frozenset([~literal]))

        for reason in solution.reasons:
            self.fill_data(reason)

        for literal in solution.literals:
            for reason in literal.imply_reasons:
                self.fill_data(reason)

        self.find_shortest_ways()

    def fill_data(self, reason):
        if len(reason.cause_literals) > 1:
            s = frozenset(reason.cause_literals)
            if s not in self.nodes:
                self.nodes[s] = NodeContainer(s)
                self.update_containers(self.nodes[s])

        cause_node = self.nodes[frozenset(reason.cause_literals)]
        literal_node = self.nodes[frozenset([reason.literal])]

        cause_node.therefore[literal_node] = reason
        literal_node.becauseof[cause_node] = reason


    def update_containers(self, node):
        for literal in node.literals:
            member = self.nodes[frozenset([literal])]
            node.members.add(member)
            member.containers.add(node)

    def find_shortest_ways(self):
        """
        This algorithm a common Dijkstra's algorithm with small modification,
        length of node of more one reason is computed as sum of it's becauseof.
        After function applying each node contains field length, the length of
        the shortest way to the initial nodes. Parent is the previous node in
        the shortest way.
        """
        queue = []
        used = set()

        def update(node, parent):
            length = 0 if node == parent else parent.length + 1
            node.length = length
            node.parent = parent
            heapq.heappush(queue, (length, node))
            for container in node.containers:
                heapq.heappush(queue, (container.length, container))

        heapq.heapify(queue)

        for node in self.initial.therefore:
            update(node, node)

        while queue:
            length, node = heapq.heappop(queue)

            if node in used:
                continue
            used.add(node)

            for cons in node.therefore:
                if cons.length > length + 1:
                    update(cons, node)

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
        new.violation_graphs = {}

        for literals, node in iteritems(self.nodes):
            new.nodes[literals.copy()] = NodeContainer(node.literals.copy())

        for literals, node in iteritems(new.nodes):
            if len(literals) > 1:
                new.update_containers(node)

        new.initial = new.nodes[frozenset()]

        return new


def path_to(source_graph, nodes):
    """
    Fills rgraph copy with reasons of shortest way to violation literals
    or violation branch
    """
    def fill(branch, node):
        if node.members:
            for member in node.members:
                fill(branch, member)
        elif node.length == 0:
            branch.fill_data(node.becauseof[source_graph.initial])
        else:
            fill(branch, node.parent)
            branch.fill_data(node.becauseof[node.parent])

    copy = source_graph.make_bare_copy()
    for node in nodes:
        if node.length == float("+inf"):
            raise Exception('No way to {0}'.format(node))
        fill(copy, node)

    return copy


def shorten_graph(rgraph, violation_nodes):
    def weight(node):
        return rgraph.nodes[frozenset([node[True]])].length + \
               rgraph.nodes[frozenset([node[False]])].length

    min_length = weight(min(violation_nodes, key = weight))

    nodes = filter(lambda node: min_length == weight(node), violation_nodes)

    literals = set()
    for node in nodes:
        literals.add(rgraph.nodes[frozenset([node[False]])])
        literals.add(rgraph.nodes[frozenset([node[True]])])

    if literals:
        return path_to(rgraph, literals)

    return path_to(rgraph, [rgraph.initial])


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
            rgraph = shorten_graph(rgraph, violation_nodes)
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


def traverse_error_graph(rgraph):
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

        if not is_visited:
            visited_nodes.add(node)
            reason_list.append(reason)

        if is_visited or not node.therefore:
            yield reason_list[:]
            reason_list[:] = []
            return

        for cons in node.therefore:
            for each in dfs(cons, node.therefore[cons]):
                yield each
            for container in cons.containers:
                process_container(container)

    def process_container(container):
        if container in visited_containers:
            return
        visited_containers.add(container)
        for ccons in container.therefore:
            if ccons not in node_deque and ccons not in visited_nodes:
                node_deque.appendleft((ccons, container.therefore[ccons]))

    for node in rgraph.initial.therefore:
        node_deque.append((node, rgraph.initial.therefore[node]))
        process_container(node)

    while node_deque:
        node, reason = node_deque.pop()
        for chain in dfs(node, reason):
            shift = 0
            while chain:
                yield chain.pop(), shift
                shift += 1
