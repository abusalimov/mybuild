"""Requirements resolver with support for rich error reporting.

This implements a general-purpose boolean formula solver, with some limitations
for sake of simplicity and real-world application. A formula is defined as a
so-called pgraph (predicate graph) whose nodes represent variables in question.
A node, in turn, consists of two literals: one for the node taking the False
value, and another for True. Graph edges are defined between these litelals and
represent node relations, e.g. dependencies.

For example, a graph for the following quite simple snippet:

    conf: foo

    module foo: {
        depends: bar(opt=0)
    }

    module bar: {
        option opt: {
            default: 42
        }
    }

... might look rather verbose:

     conf      =>    foo              ~foo       =>   ~conf

     foo       =>    bar              ~bar       =>   ~foo
     foo       =>    opt=0            ~opt=0     =>   ~foo

     opt=0     =>    bar              ~bar       =>   ~opt=0
     opt=42    =>    bar              ~bar       =>   ~opt=42
     opt=0     =>   ~opt=42            opt=42    =>   ~opt=0
     opt=42    =>   ~opt=0             opt=0     =>   ~opt=42

    (  bar   AND ~opt=0  )   =>    opt=42
    (  bar   AND ~opt=42 )   =>    opt=0
    ( ~opt=0 AND ~opt=42 )   =>   ~bar

As you can see is a rather low-level structure, but this way we gain a precise
control over how things work under the hood.

Another responsibility of this module is to be able to provide a human-readable
error message in case of a conflict, or some explanatory text about decisions
taken by an explicit request from the user.

Referring to the example above, that could look something like:

    Option 'opt' of module 'bar' takes value 0
        As required by module 'foo'
            Required by the root 'conf'

Sub-modules of the `mybuild.req` package:

    * `mybuild.req.pgraph`: Defines Pgraph, Node, Literal and other types.

    * `mybuild.req.solver`: The algorithm itself; given a pgraph finds a
      solution, i.e. assigns a boolean value for every its node.

    * `mybuild.req.rgraph`: Extracts the shortest path in a reasoning graph
      that leads to a conflict and formats an error message for the user.
"""
from __future__ import absolute_import, division, print_function
from mybuild._compat import *


__author__ = "Eldar Abusalimov"
__date__ = "2012-11-29"
