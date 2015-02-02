"""
Unit tests for mylang.parse
"""

__author__ = "Vita Loginova"
__date__ = "2015-02-02"

from _compat import *

import ast
import itertools

import unittest

from mylang.parse import my_parse


class ASTComparator(object):
    """
    A node a in an AST A is equal to a node b in an AST B <=>
        1. The node a has the same type as the node b;
        2. The node a appears in the same place in the AST A as the node
           b appears in the AST B and vice versa;
        3. Each child of the node a is equal to some child of the node b and
           vice versa.
    """
    def __init__(self):
        super(ASTComparator, self).__init__()
        self.names_a = {}
        self.names_b = {}

    def compare(self, node_a, node_b):
        # This function is not reentrant as it fills self.names_a and
        # self.names_b
        if type(node_a) != type(node_b):
            return False

        if isinstance(node_a, ast.AST):
            for k, v in iteritems(vars(node_a)):
                if k in ('lineno', 'col_offset', 'ctx'):
                    continue
                if not self.compare(v, getattr(node_b, k)):
                    return False
            return True

        if isinstance(node_a, list):
            return all(itertools.starmap(self.compare, zip(node_a, node_b)))

        if isinstance(node_a, str):

            if node_a in self.names_a and node_b in self.names_b:
                return self.names_a[node_a] == node_b

            elif node_a not in self.names_a and node_b not in self.names_b:
                self.names_a[node_a] = node_b
                self.names_b[node_b] = node_a
                return True

            else:
                # print(node_a, node_b)
                return False

        return node_a == node_b


class ParserTestCase(unittest.TestCase):

    def test_empty_module(self):
        py_source = """
try:
    @__my_exec_module__
    def _main_():
        global __name__
        _module_ = __name__

        def func_main(self):
            return __my_new_type__(module, 'main', _module_, None, [])

        return [('main', func_main, False)]

        pass
except __my_exec_module__:
    pass
"""

        my_source = """
module main: {
}
"""
        py_node = ast.parse(py_source, mode='exec')
        my_node = my_parse(my_source)

        self.assertIs(True, ASTComparator().compare(my_node, py_node))

    def test_different_namespace_declaration(self):
        my_source1 = """
module main: {
    a: {
        b: {
            c: 3
            d: 1
        }
        e: 2
    }

    f: 3
}
"""
        my_source2 = """
module main: {
    a.e: 2
    f: 3
    a.b.c: 3
    a.b.d: 1
}
"""
        my_node1 = my_parse(my_source1)
        my_node2 = my_parse(my_source2)

        self.assertIs(True, ASTComparator().compare(my_node1, my_node1))


    def test_modules_and_types(self):
        py_source = """
try:
    @__my_exec_module__
    def _trampoline_():
        global __name__
        _module_ = __name__

        def func_foo(self):

            def func_files(self):
                return ['foo.c']

            return __my_new_type__(module, 'foo', _module_, None,
                                   [('files', func_files, False)])

        def func_bool(self):
            return __my_new_type__(type, 'bool', _module_, None, [])

        return [('bool', func_bool, False), ('foo', func_foo, False)]
except __my_exec_module__:
    pass
"""
        my_source = """
module foo: {
    files: ["foo.c"]
}

type bool: {
}
"""

        py_node = ast.parse(py_source, mode='exec')
        my_node = my_parse(my_source)

        self.assertIs(True, ASTComparator().compare(my_node, py_node))
        pass


    # Tuples, lists, dictionaries, function calls.
    def test_different_values(self):
        py_source = """
try:
    @__my_exec_module__
    def _trampoline_():
        global __name__
        _module_ = __name__

        def func_call(self):
            return func(s, d, f, x=0, y=1, z=2)

        def func_list(self):
            return [1, 2, 3, 4]

        def func_dict(self):
            return {'a': 1, 'b': 2, 'c': 3, 'd': 4}

        def func_empty(self):
            return {}

        def func_tuple(self):
            return (1, 2, 3, 4)

        return [('call', func_call, False), ('dict', func_dict, False),
                ('empty_dict', func_empty, False), ('list', func_list, False),
                ('tuple', func_tuple, False)]
except __my_exec_module__:
    pass
"""

        my_source = """
call: func(s, d, f, x=0, y=1, z=2)
list: [1, 2, 3, 4]
dict: ["a":1, "b":2, "c":3, "d":4]
empty_dict: [:]
tuple: (1, 2, 3, 4)
"""
        py_node = ast.parse(py_source, mode='exec')
        my_node = my_parse(my_source)

        self.assertIs(True, ASTComparator().compare(my_node, py_node))


    # TODO
    def test_expression_computing_order(self):
        py_source = """"""
        my_source = """"""

        py_node = ast.parse(py_source, mode='exec')
        my_node = my_parse(my_source)

        self.assertIs(True, ASTComparator().compare(my_node, py_node))
        pass


def suite():
    import sys
    return unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])


if __name__ == '__main__':
    import util, sys, logging
    # util.init_logging(filename='%s.log' % __name__)
    util.init_logging(sys.stderr,
                      level=logging.DUMP)

    unittest.main()
