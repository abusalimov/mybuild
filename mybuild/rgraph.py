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

        def push(node):
            heapq.heappush(queue, (node.length, node))

        def pop():
            node = heapq.heappop(queue)[1]
            if node in used:
                return pop()
            used.add(node)
            return node

        for node in self.initial.therefore:
            node.length = 0
            node.parent = node
            push(node)
            for container in node.containers:
                push(container)

        heapq.heapify(queue)

        while queue:
            try:
                node = pop()
            except IndexError:
                continue

            for cons in node.therefore:
                if cons.length > node.length + 1:
                    cons.length = node.length + 1
                    cons.parent = node
                    push(cons)
                    for container in cons.containers:
                        push(container)

        logger.debug('Lengths for shortest ways to {0}'.format(self))
        for node in itervalues(self.nodes):
            logger.debug('{0}: length {1}'.format(node, node.length))

def way_to(source_graph, nodes):
    """
    Fills rgraph copy with reasons of shortest way to violation literals
    or violation branch
    """
    def fill(branch, node):
        if node.length == 0:
            if not node.members:
                branch.fill_data(node.becauseof[source_graph.initial])
            else:
                for member in node.members:
                    fill(branch, member)
            return;

        if not node.members:
            fill(branch, node.parent)
            branch.fill_data(node.becauseof[node.parent])
            return
        else:
            for member in node.members:
                fill(branch, member)
            return

    copy = branch_copy(source_graph)
    for node in nodes:
        if node.length == float("+inf"):
            raise Exception('No way to {0}'.format(node))
        fill(copy, node)

    return copy

def shorten_branch(trunk, branch, rgraph_branch, violation_nodes):
    min_length = float("+inf")
    min_node = None
    #try to find shortest way to violation nodes
    for node in violation_nodes:
        length = rgraph_branch.nodes[frozenset([node[True]])].length + \
                rgraph_branch.nodes[frozenset([node[False]])].length
        if length < min_length:
            min_length = length
            min_node = node

    if min_node is not None:
        nodes = set()
        nodes.add(rgraph_branch.nodes[frozenset([min_node[True]])])
        nodes.add(rgraph_branch.nodes[frozenset([min_node[False]])])
        return way_to(rgraph_branch, nodes)

    if rgraph_branch.initial.length != float("+inf"):
        return way_to(rgraph_branch, set([rgraph_branch.initial]))

    #Actually, it can't be, otherwise how we get violation?
    raise Exception('No ways to some violation branch or violation nodes {0} '
                    'in branch {1}'.format(violation_nodes, branch))

def branch_copy(branch):
    """
    Returns rgraph with same nodes but without any reason
    """
    cls = type(branch)
    new = cls.__new__(cls)

    new.nodes = {}
    for literals, node in iteritems(branch.nodes):
        new.nodes[literals.copy()] = NodeContainer(node.literals.copy())
    for literals, node in iteritems(new.nodes):
        if len(literals) > 1:
            new.update_containers(node)

    new.violation_graphs = {}
    new.initial = new.nodes[frozenset()]

    return new

def get_violation_nodes(solution):
    violation_nodes = set()
    literals = solution.literals
    nodes = solution.nodes
    for node in nodes:
        if node[False] in literals and node[True] in literals:
            violation_nodes.add(node)
    return violation_nodes

def create_rgraph_branch(trunk, branch, parent_rgraph):
    solution = branch.flatten()
    #TODO move to solver
    for gen_literal in branch.gen_literals:
        solution.reasons.add(Reason(gen_literal))
    for literal in solution.literals:
        for reason in literal.imply_reasons:
            if (literal not in trunk.dead_branches or
                literal in branch.gen_literals):
                solution.reasons.add(reason)
    rgraph = Rgraph(solution)
    return shorten_branch(trunk, branch, rgraph, get_violation_nodes(branch))

def get_rgraph_way(rgraph, literals):
    nodes = set()
    for literal in literals:
        nodes.add(rgraph.nodes[frozenset([literal])])
    rgraph_way = way_to(rgraph, nodes)
    rgraph_way.violation_graphs = rgraph.violation_graphs
    return rgraph_way

def get_rgraph(trunk):
    rgraph = Rgraph(trunk)
    for literal in trunk.literals:
        for reason in literal.imply_reasons:
            rgraph.fill_data(reason)
    #It will better if this function will run just one time, but adding reasons
    #to trunk it ruins flatten()
    rgraph.find_shortest_ways()

    branchmap = {}
    for literal, branch in iteritems(trunk.dead_branches):
        if branch.valid:
            continue

        if frozenset(branch.gen_literals) in branchmap:
            rgraph_branch = branchmap[frozenset(branch.gen_literals)]
            rgraph.violation_graphs[literal] = rgraph_branch
            continue

        rgraph_branch = create_rgraph_branch(trunk, branch, rgraph)
        rgraph_branch.violation_graphs = rgraph.violation_graphs
        branchmap[frozenset(branch.gen_literals)] = rgraph_branch
        rgraph.violation_graphs[literal] = rgraph_branch

    return rgraph

def get_error_rgraph(solution_error):
    solution = solution_error.trunk
    rgraph = get_rgraph(solution)

    violation_nodes = get_violation_nodes(solution)
    literals = set()
    for node in violation_nodes:
        literals.add(node[False])
        literals.add(node[True])
    # print 'violation_nodes:', violation_nodes
    return get_rgraph_way(rgraph, literals)

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
