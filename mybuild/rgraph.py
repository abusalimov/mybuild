"""
Graph for reasons of pgraph solution 
"""

__author__ = "Vita Loginova"
__date__ = "2013-06-28"

import sys
import Queue

class Node(object):
    """meta types for nodes in reason graph"""
    def __init__(self):
        self.consequenses = set()
        self.reasons = set()
        self.length = sys.maxint
        
    def compare_literals(self, literals):
        return False
    
    def get_literals(self):
        return set()
        
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
        self.nodes = set() 
        self.initials = set() 
        
        for l in literals:
            node = SingleNode(l)
            self.nodes.add(node)
            
        for r in reasons:
            if len(r.cause_literals) > 1:
                node = MultipleNode(set(r.cause_literals))
                self.nodes.add(node)
            if len(r.cause_literals) == 0:
                s = set()
                s.add(r.literal)
                self.initials.add(self.get_node_by_literals(s))
                
        for r in reasons:
            if len(r.cause_literals) > 0:
                self.fill_data(r)
        
    def get_node_by_literals(self, literals): 
        for n in self.nodes:
            if n.compare_literals(literals):
                return n
    
    def fill_multiple_node(self, node):
        for n in self.nodes:
            for r in node.literals:
                if isinstance(n, SingleNode) and r == n.literal:
                    n.consequenses.add(node) 
                    node.reasons.add(n)       
            
    def fill_data(self, reason):
        for n in self.nodes:
            if n.compare_literals(reason.cause_literals):
                s = set()
                s.add(reason.literal)
                n.consequenses.add(self.get_node_by_literals(s))
            if isinstance(n, SingleNode) and reason.literal == n.literal:
                n.reasons.add(self.get_node_by_literals(reason.cause_literals))
            if isinstance(n, MultipleNode):
                self.fill_multiple_node(n)
    
    '''
    Simple way to print reason graph. Multiple nodes are printed in new line without offset.
    ToDo: print by using reason.why
    '''
    def print_graph(self):
        queue = Queue.LifoQueue()
        used = set()
        
        for node in self.initials:
            queue.put(node)
        
        while not queue.empty():        
            self.dfs(queue.get(), node.reasons, used, queue, 0)
                
    def dfs(self, node, reason, used, queue, depth):
        if node in used:
            print self.get_offset(depth), node.get_literals(), 'because of', reason
            return
        
        used.add(node)
        print self.get_offset(depth), node.get_literals(), 'because of', reason
        for cons in node.consequenses:
            if isinstance(cons, SingleNode):
                self.dfs(cons, node.get_literals(), used, queue, depth + 1)
            if isinstance(cons, MultipleNode) and cons not in queue.queue:
                queue.put(cons)
    
    def get_offset(self, depth):
        st = ''  
        for i in range(0, depth) :
            st = st + '  '  
        return st
    
    '''
    This algorithm a common  Dijkstra's algorithm with small modification:
    if node is Multiple then we put it in end of stack and handle it later.
    We do this because of proposition that cost of node gained before
    rest multiple nodes and they's consequences is minimal. (TODO: modify).
    After function applying each node contains field length, the length of 
    the shortest way to the initial nodes. If node is Single it also contains
    parent - the previous node in the shortest way. If node is Multiple then
    its parents are reasons.
    '''            
    def find_shortest_ways(self):
        stack = []
        used = set()
        for node in self.initials:
            stack.append(node)
            node.length = 0
            node.parent = node
            used.add(node)
            
        while stack:
            node = stack.pop()
            
            if isinstance(node, MultipleNode):
                    node.length = 0;
                    for r in node.reasons:
                        node.length += r.length
            
            for cons in node.consequenses:
                if isinstance(cons, SingleNode):
                    if cons.length > node.length + 1:
                        cons.length = node.length + 1
                        cons.parent = node
                    if cons not in used:      
                        stack.append(cons)
                        used.add(cons)
                        
                if isinstance(cons, MultipleNode):   
                    if cons not in used:      
                        stack.insert(0, cons)   
                        used.add(cons)