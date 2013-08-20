"""
Graph for reasons of pgraph solution 
"""

__author__ = "Vita Loginova"
__date__ = "2013-06-28"

from  _compat import *

import Queue
import heapq

from mybuild.pgraph import Reason

from util.operator import getter
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
        self.solution = solution
        self.initial = NodeContainer(set())  
        self.nodes = {}    
        self.nodes[frozenset(set())] = self.initial
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
     
    def get_shortest_way(self, literal):
        if self.nodes.length == float("+inf"):
            raise Exception
        
                        
    def print_graph(self):
        """
        Simple way to print reason graph. Nodes of more one reason are printed 
        in new line without offset.
        """
        queue = Queue.LifoQueue()
        used = set()
        
        #queue contains touples (node, reason)
        for node in self.initial.therefore:
            queue.put((node, self.initial.therefore[node]))
            self._process_containers_dfs(node, used, queue)
        
        while not queue.empty():
            node, reason = queue.get()        
            self.dfs(node, reason, used, queue, 0)
                
    def dfs(self, node, reason, used, queue, depth):
        if node in used:
            self.print_reason(reason,depth)
            return
        
        used.add(node)
        self.print_reason(reason,depth)
        for cons in node.therefore:
            self.dfs(cons, node.therefore[cons], used, queue, depth + 1)
            self._process_containers_dfs(cons, used, queue)
                            
    def _process_containers_dfs(self, node, used, queue):
        for container in node.containers:
            if container not in used:
                used.add(container)
                for ccons in container.therefore:
                    if node not in queue.queue:
                        queue.put((ccons, container.therefore[ccons]))
                            
    def print_reason(self, reason, depth):
        print '  ' * depth, reason

def way_to(source_graph, nodes):
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
        fill(copy, node)
        
    return copy

def shorten_branch(trunk, branch, rgraph_branch, violation_nodes):                  
    min_length = float("+inf")   
    min_node = None                   
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
    
    min_literal = None                
    for literal in iterkeys(trunk.dead_branches):
        if frozenset([literal]) in rgraph_branch.nodes and \
                literal not in branch.gen_literals: 
            length = rgraph_branch.nodes[frozenset([literal])].length
            if length < min_length:
                min_length = length
                min_literal = literal
            
    if min_literal is not None:
        nodes = set()
        nodes.add(rgraph_branch.nodes[frozenset([min_literal])])
        return way_to(rgraph_branch, nodes)
    
    raise Exception

def branch_copy(branch):
    cls = type(branch)
    new = cls.__new__(cls)

    new.solution = branch.solution
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
    for gen_literal in branch.gen_literals:
        solution.reasons.add(Reason(None, gen_literal))     
    for literal in solution.literals:
        for reason in literal.imply_reasons:
            if literal not in trunk.dead_branches or literal in branch.gen_literals:
                solution.reasons.add(reason)
    rgraph = Rgraph(solution)
    return shorten_branch(trunk, branch, rgraph, get_violation_nodes(branch))  

def get_rgraph(trunk):
    rgraph = Rgraph(trunk)
    
    def add_violation_branch(literal, rgraph_branch):
        rgraph.violation_graphs[literal] = rgraph_branch
    
    branchmap = {}  
    for literal, branch in iteritems(trunk.dead_branches):
        if frozenset(branch.gen_literals) in branchmap:
            rgraph_branch = branchmap[frozenset(branch.gen_literals)]
            add_violation_branch(literal, rgraph_branch)
            continue
        
        rgraph_branch = create_rgraph_branch(trunk, branch, rgraph) 
#         rgraph_branch.print_graph()
#         print '---'
        branchmap[frozenset(branch.gen_literals)] = rgraph_branch
        add_violation_branch(literal, rgraph_branch)
    
    #rgraph.print_graph()
        
    return rgraph
    
    