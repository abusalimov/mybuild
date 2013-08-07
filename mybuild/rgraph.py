"""
Graph for reasons of pgraph solution 
"""

__author__ = "Vita Loginova"
__date__ = "2013-06-28"

import sys
import Queue
from mybuild.pgraph import *

class NodeContainer(object):
    def __init__(self, literals):
        self.literals = frozenset(literals) 
        self.containers = set() #NodeContainrs set that contains nodes with
                                #current node as member 
        self.members = set()    #Node set of nodes with one literal from 
                                #node.literals
        self.therefore = {} #key = node, value = reason
        self.becauseof = {} #key = node, value = reason
        self.length = float("+inf")
        self.parent = None
        
    def __lt__(self, other):
        return self.length < other.length
    
    def compare_literals(self, literals):
        return (set(literals) == self.literals)
    
# TODO remove to other place after all types why function realization
def why_violation(cls, literal, *cause_literals):
    return '%s because of violation %s' % (literal, cause_literals)  

class Rgraph(object): 
    """
    Rgraph or Reason graph
    """  
    def __init__(self, literals, reasons, violation_branches = set()):
        self.violation_branches = violation_branches
        self.initial = NodeContainer(set())  
        self.nodes = {}    
        self.nodes[frozenset(set())] = self.initial
        
        for literal in literals:
            self.nodes[frozenset([literal])] = NodeContainer(frozenset([literal]))
                
        for reason in reasons:
            self.fill_data(reason)
              
        for branch in violation_branches:
            for literal in branch.gen_literals:
                self.fill_data(Reason(why_violation, ~literal, literal))
                self.fill_data(Reason(None, literal))  
         
    def fill_data(self, reason): 
        if len(reason.cause_literals) > 1:
            s = frozenset(reason.cause_literals)
            self.nodes[s] = NodeContainer(s)
            self.update_containers(self.nodes[s])
        elif frozenset(reason.cause_literals) not in self.nodes:
            self.nodes[frozenset(reason.cause_literals)] = NodeContainer(frozenset(reason.cause_literals))
            
        if frozenset([reason.literal]) not in self.nodes:
            self.nodes[frozenset([reason.literal])] = NodeContainer(frozenset([reason.literal]))
                     
        cause_node = self.nodes[frozenset(reason.cause_literals)]
        literal_node = self.nodes[frozenset([reason.literal])]
        
        cause_node.therefore[literal_node] = reason
        literal_node.becauseof[cause_node] = reason
        
    def update_containers(self, node):
        for literal in node.literals:
            member = self.nodes[frozenset([literal])]
            node.members.add(member)
            member.containers.add(node)  
    
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
            
        for branch in self.violation_branches:     
            branch.trunk |= branch 
            violation_nodes = self.get_violation_nodes(branch.trunk)
            
            print '--- violation for', branch.gen_literals, '---'
            for literal in branch.gen_literals:
                branch.trunk.reasons.add(Reason(None, literal))
            rgraph_branch = Rgraph(branch.trunk.literals, branch.trunk.reasons)
            rgraph_branch.find_shortest_ways()
            
#             for node in rgraph_branch.nodes.values():
#                 print node.literals, node.length
                
            for node in violation_nodes:
                print '------ because of {0} and {1} ------'.format(node[True], node[False])
                rgraph_branch.print_shortest_way(node[True])
                rgraph_branch.print_shortest_way(node[False])
                print '------'
            print '---'
            
    def get_violation_nodes(self, trunk):
        violation_nodes = set()
        for node in trunk.nodes:
            if node[False] in trunk.literals and node[True] in trunk.literals:
                violation_nodes.add(node)
        return violation_nodes
                
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
               
    def find_shortest_ways(self):
        """
        This algorithm a common Dijkstra's algorithm with small modification,
        length of node of more one reason is computed as sum of it's becauseof.
        After function applying each node contains field length, the length of 
        the shortest way to the initial nodes. Parent is the previous node in 
        the shortest way.
        """ 
        queue = Queue.PriorityQueue()
        used = set()
        for node in self.initial.therefore:
            queue.put_nowait(node)
            node.length = 0
            node.parent = node
            used.add(node) 
            self._process_containers_shortest_ways(node, used, queue)
            
        while not queue.empty():
            node = queue.get_nowait()
                     
            for cons in node.therefore:
                if cons.length > node.length + 1:
                    cons.length = node.length + 1
                    cons.parent = node
                        
                if cons not in used:      
                    queue.put_nowait(cons)
                    used.add(cons)
                
                self._process_containers_shortest_ways(cons, used, queue)

                    
    def _process_containers_shortest_ways(self, node, used, queue):         
        for container in node.containers:
            container.length = sum(r.length for r in container.members)
            if container not in used:
                used.add(container)
                queue.put_nowait(container)

    def print_shortest_way(self, literals):
        node = self.nodes[frozenset([literals])]    
        if node.length == float("+inf"):
            return    
        self._print_shortest_way_part(node)
         
    def _print_shortest_way_part(self, node):
        if node.length == 0:
            self.print_reason(node.becauseof[self.initial], 0)
            return 1;
               
        if not node.members:
            depth = self._print_shortest_way_part(node.parent)
            self.print_reason(node.becauseof[node.parent], depth)
            return depth + 1
        else:
            for member in node.members:
                self._print_shortest_way_part(member)
            return 0

