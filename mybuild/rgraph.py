"""
Graph for reasons of pgraph solution 
"""

__author__ = "Vita Loginova"
__date__ = "2013-06-28"

class Node:
    """meta types for nodes in reason graph"""
    def __init__(self):
        self.consequenses = set()
        self.reasons = set()
        self.isInitial = False
        
    def compare_literals(self, literals):
        return False
    
    def get_literals(self):
        return set()
        
class SingleNode(Node):
    """type for nodes containing only one literal"""   
    def __init__(self, literal):
        Node.__init__(self)
        self.literal = literal
        
    def compare_literals(self, literals):
        if len(literals) != 1:
            return False
        for literal in literals:
            if literal != self.literal:
                return False
        return True
    
    def get_literals(self):
        s = set();
        s.add(self.literal)
        return s
        
        
class MultipleNode(Node):
    """type for nodes containing two or more literals"""  
    def __init__(self, literals):
        Node.__init__(self)
        self.literals = literals
        
    def compare_literals(self, literals):
        if len(literals) != len(self.literals):
            return False
        for literal in literals:
            if not (literal in self.literals):
                return False
        return True 
    
    def get_literals(self):
        return self.literals

class Rgraph(object): 
    """
    Rgraph or Reason graph is a graph of two node types. Each node has reasons
    and consequences. Reasons is node set, each of that enough for node
    correctness. Consequences is node set, each of that correct because of node.
    """  
    
    def __init__(self, initial_values, literals, reasons):
        self.nodes = set()  
        for r in reasons:
            if len(r.cause_literals) > 1:
                node = MultipleNode(self.convert_to_set(r.cause_literals))
                self.nodes.add(node)
        for l in literals:
            node = SingleNode(l)
            self.nodes.add(node)
        for r in reasons:
            self.fill_data(r)
        #self.mark_initial_states(initial_values)
    
    def convert_to_set(self, literals): 
        s = set()
        for l in literals:
            s.add(l) 
        return s  
        
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