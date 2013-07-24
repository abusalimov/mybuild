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
        self.literals = literals 
        self.containers = set() #NodeContainrs set that contains nodes with current node as member 
        self.members = set() #Node set of nodes with one literal from node.literals
        self.consequences = {} #key = node, value = reason
        self.reasons = {} #key = node, value = reason
        self.length = float("+inf")
        self.parent = None
        
    def __lt__(self, other):
        return self.length < other.length
    
    def compare_literals(self, literals):
        return (set(literals) == self.literals)

class Rgraph(object): 
    """
    Rgraph or Reason graph
    """  
    def __init__(self, literals, reasons):
        self.initial = NodeContainer(set())  
        self.nodes = set()   
        self.nodes.add(self.initial)
        
        for literal in literals:
            self.nodes.add(NodeContainer(self.literal_to_set(literal)))
                
        for reason in reasons:
            self.fill_data(reason)
            
    def literal_to_set(self, literal):
        s = set()
        s.add(literal)
        return s
                
    def update_containers(self, node):
        for literal in node.literals:
            member = self.get_node_by_literals(self.literal_to_set(literal))
            node.members.add(member)
            member.containers.add(node)
        
    def get_node_by_literals(self, literals): 
        for n in self.nodes:
            if n.compare_literals(literals):
                return n                      
            
    def fill_data(self, reason): 
        if len(reason.cause_literals) > 1:
            s = set(reason.cause_literals)
            self.nodes.add(NodeContainer(s))
            self.update_containers(self.get_node_by_literals(s))
                      
        cause_node = self.get_node_by_literals(reason.cause_literals)
        literal_node = self.get_node_by_literals(self.literal_to_set(reason.literal))
        
        cause_node.consequences[literal_node] = reason
        literal_node.reasons[cause_node] = reason
    
    def print_graph(self):
        """
        Simple way to print reason graph. Nodes of more one reason are printed in new line without offset.
        """
        queue = Queue.LifoQueue()
        used = set()
        
        #queue contains touples (node, reason)
        for node in self.initial.consequences:
            queue.put((node, self.initial.consequences[node]))
        
        while not queue.empty():
            node = queue.get()        
            self.dfs(node[0], node[1], used, queue, 0)
                
    def dfs(self, node, reason, used, queue, depth):
        if node in used:
            self.print_reason(reason,depth)
            return
        
        used.add(node)
        self.print_reason(reason,depth)
        for cons in node.consequences:
            self.dfs(cons, node.consequences[cons], used, queue, depth + 1)
            for container in cons.containers:
                if container not in used:
                    used.add(container)
                    for ccons in container.consequences:
                        if cons not in queue.queue:
                            queue.put((ccons, container.consequences[ccons]))
                            
    def print_reason(self, reason, depth):
        print self.get_offset(depth), reason.why(reason, reason.literal, reason.cause_literals)
    
    def get_offset(self, depth):
        st = ''  
        for i in range(0, depth) :
            st = st + '  '  
        return st
               
    def find_shortest_ways(self):
        """
        This algorithm a common Dijkstra's algorithm with small modification,
        length of node of more one reason is computed as sum of it's reasons.
        After function applying each node contains field length, the length of 
        the shortest way to the initial nodes. Parent is the previous node in 
        the shortest way.
        """ 
        stack = Queue.PriorityQueue()
        used = set()
        for node in self.initial.consequences:
            stack.put_nowait(node)
            node.length = 0
            node.parent = node
            used.add(node)
            
        while not stack.empty():
            node = stack.get_nowait()
                 
            for cons in node.consequences:
                if cons.length > node.length + 1:
                    cons.length = node.length + 1
                    cons.parent = node
                        
                if cons not in used:      
                    stack.put_nowait(cons)
                    used.add(cons)
                    for container in cons.containers:
                        container.length = sum(r.length for r in container.members)
                        if container not in used:
                            used.add(container)
                            stack.put_nowait(container)
                    
                    
                    