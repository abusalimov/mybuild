"""
Graph for reasons of pgraph solution 
"""

__author__ = "Vita Loginova"
__date__ = "2013-06-28"

import sys
import Queue
from mybuild.pgraph import *

class Node(object):
    """meta types for nodes in reason graph"""
    def __init__(self):
        self.consequences = set()
        self.reasons = set()
        self.length = float("+inf")
        
    def compare_literals(self, literals):
        return False
    
    def get_literals(self):
        return set()
    
    def __lt__(self, other):
        return self.length < other.length
        
class SingleNode(Node):
    """type for nodes containing only one literal"""   
    def __init__(self, literal):
        super(SingleNode, self).__init__()
        self.literal = literal
        
    def compare_literals(self, literals):
        return len(literals) == 1 and self.literal in set(literals)
    
    def get_literals(self):
        s = set();
        s.add(self.literal)
        return s
        
        
class MultipleNode(Node):
    """type for nodes containing two or more literals"""  
    def __init__(self, literals):
        super(MultipleNode, self).__init__()
        self.literals = literals
        
    def compare_literals(self, literals):
        return (set(literals) == self.literals)
    
    def get_literals(self):
        return self.literals

class Rgraph(object): 
    """
    Rgraph or Reason graph is a graph of two node types. Each node has reasons
    and consequences. Reasons is node set, each of that enough for node
    correctness. Consequences is node set, each of that correct because of node.
    """  
    
    def __init__(self, literals, reasons):
        self.initials = set() 
        
        self.nodes = set(SingleNode(literal) for literal in literals)
            
        for r in reasons:
            if len(r.cause_literals) > 1:
                node = MultipleNode(set(r.cause_literals))
                self.nodes.add(node)
            if not r.cause_literals:
                s = set()
                s.add(r.literal)
                touple = self.get_node_by_literals(s), r
                self.initials.add(touple)
                
        for r in reasons:
            if r.cause_literals:
                self.fill_data(r)
        
        for n in self.nodes:        
            if isinstance(n, MultipleNode):
                self.fill_multiple_node(n)
        
    def get_node_by_literals(self, literals): 
        for n in self.nodes:
            if n.compare_literals(literals):
                return n
    
    def fill_multiple_node(self, node):
        for n in self.nodes:
            for r in node.literals:
                if isinstance(n, SingleNode) and r == n.literal:
                    reason = Reason(None, n.literal, *node.literals)
                    touple = n, reason
                    node.reasons.add(touple)   
                    touple = node, reason
                    n.consequences.add(touple) 
                        
            
    def fill_data(self, reason):
        for n in self.nodes:
            if n.compare_literals(reason.cause_literals):
                s = set()
                s.add(reason.literal)
                touple = self.get_node_by_literals(s), reason
                n.consequences.add(touple)
            if isinstance(n, SingleNode) and reason.literal == n.literal:
                touple = self.get_node_by_literals(reason.cause_literals), reason
                n.reasons.add(touple)
            
    
    def print_graph(self):
        """
        Simple way to print reason graph. Multiple nodes are printed in new line without offset.
        ToDo: print by using reason.why
        """
        queue = Queue.LifoQueue()
        used = set()
        
        for node in self.initials:
            queue.put(node)
        
        while not queue.empty():        
            self.dfs(queue.get(), used, queue, 0)
                
    def dfs(self, node, used, queue, depth):
        if node[0] in used:
            print self.get_offset(depth), node[1].why(node[1], node[1].literal, node[1].cause_literals)
            return
        
        used.add(node[0])
        print self.get_offset(depth), node[1].why(node[1], node[1].literal, node[1].cause_literals)
        for cons in node[0].consequences:
            if isinstance(cons[0], SingleNode):
                self.dfs(cons, used, queue, depth + 1)
            if isinstance(cons[0], MultipleNode) and cons[0] not in queue.queue:
                queue.put(cons)
    
    def get_offset(self, depth):
        st = ''  
        for i in range(0, depth) :
            st = st + '  '  
        return st
               
    def find_shortest_ways(self):
        """
        This algorithm a common  Dijkstra's algorithm with small modification,
        length of Multiple node is computed as sum of it's reasons.
        After function applying each node contains field length, the length of 
        the shortest way to the initial nodes. If node is Single it also contains
        parent - the previous node in the shortest way. If node is Multiple then
        its parents are reasons.
        """ 
        stack = Queue.PriorityQueue()
        used = set()
        for node in self.initials:
            stack.put_nowait(node[0])
            node[0].length = 0
            node[0].parent = node[0]
            used.add(node[0])
            
        while not stack.empty():
            node = stack.get_nowait()
                 
            for cons in node.consequences:
                if isinstance(cons[0], SingleNode):
                    if cons[0].length > node.length + 1:
                        cons[0].length = node.length + 1
                        cons[0].parent = node
                            
                if isinstance(cons[0], MultipleNode):
                    cons[0].length = sum(r[0].length for r in cons[0].reasons)
                        
                if cons[0] not in used:      
                    stack.put(cons[0], False)
                    used.add(cons[0])
                    
                    
                    