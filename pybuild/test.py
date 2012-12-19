
import unittest

from exception import *

from package import Package, obj_in_pkg
from scope   import Scope
from ops     import add_many, cut_many, cut, fixate

from option  import Boolean, List, Integer
from domain  import BoolDom, ListDom, IntegerDom, Domain, ModDom

from module  import Module
from interface import Interface

def module_package(package, name, *args, **kargs):
    obj_in_pkg(Module, package, name, *args, **kargs)

class TestCase(unittest.TestCase):
    def test_recursive_feature_add(self):
        package = Package('root')
        module_package(package, 'blck')
        module_package(package, 'stdio')
        module_package(package, 'fs', depends = ['blck', 'stdio'])
        module_package(package, 'test')
        module_package(package, 'test2', depends = ['test'])
        module_package(package, 'test3')

        scope = Scope()
        scope = add_many(scope, map(lambda s: package[s], ['blck', 'stdio', 'fs', 'test', 'test2', 'test3']))

        scope = cut_many(scope, [(package['fs'], BoolDom([True])), (package['test2'], BoolDom([True]))])

        final = fixate(scope)
        
        self.assertEqual(final[package['blck']],  BoolDom([True]))
        self.assertEqual(final[package['stdio']], BoolDom([True]))
        self.assertEqual(final[package['fs']],    BoolDom([True]))
        self.assertEqual(final[package['test']],  BoolDom([True]))
        self.assertEqual(final[package['test2']], BoolDom([True]))
        self.assertEqual(final[package['test3']], BoolDom([False]))

    def test_depends_with_options(self):
        package = Package('root')
        module_package(package, 'stack', options = [Integer('stack_sz', domain = range(8192,1000000))])
        module_package(package, 'thread_core', depends = [ ('stack', {'stack_sz' : IntegerDom([16000])}) ])

        scope = Scope()
        scope = add_many(scope, map(lambda s: package[s], ['stack', 'thread_core']))

        scope = cut_many(scope, [(package['stack'], BoolDom([True])), (package['thread_core'], BoolDom([True]))])

        final = fixate(scope)

        self.assertTrue(final[package['thread_core']])
        self.assertTrue(final[package['stack']])
        self.assertEqual(final[package['stack.stack_sz']], Domain([16000]))

    def test_depends_with_list(self):
        package = Package('root')

        def incl_trigger(scope, find_fn):
            opt = find_fn('lds.sections')
            return cut(scope, opt, ListDom(['test']))

        module_package(package, 'lds', options = [List('sections')])
        module_package(package, 'stack_lds', depends = [ 'lds' ], include_trigger=incl_trigger)

        scope = Scope()
        scope = add_many(scope, map(lambda s: package[s], ['lds', 'stack_lds']))

        scope = cut_many(scope, [(package['stack_lds'], BoolDom([True]))])

        final = fixate(scope)

        self.assertTrue(final[package['lds']])
        self.assertTrue(final[package['stack_lds']])
        self.assertEqual(len(final[package['lds.sections']]), 1)

    def test_depends_with_options2(self):
        package = Package('root')
        module_package(package, 'stack', options = [Integer('stack_sz', domain = range(8192,12000))])
        module_package(package, 'thread_core', depends = [ ('stack', {'stack_sz' : Domain([16000])}) ])

        scope = Scope()
        scope = add_many(scope, map(lambda s: package[s], ['stack', 'thread_core']))


        self.assertRaises(CutConflictException, cut, scope, package['thread_core'], BoolDom([True]))

    def test_optional_include(self):
        package = Package('root')
        module_package(package, 'amba')

        def uart_trigger(scope, find_fn):
            opt = find_fn('uart.amba_pp')
            if opt.value(scope):
                return cut(scope, package['amba'], BoolDom([True]))
            return scope

        module_package(package, 'uart', options = [Boolean('amba_pp')] , include_trigger=uart_trigger)
        
        scope = Scope()
        scope = add_many(scope, [package['uart'], 
                         package['amba']])

        scope = cut_many(scope, [(package['uart'], BoolDom([True])), 
                                 (package['uart.amba_pp'], BoolDom([True]))])

        self.assertTrue(scope != False)

        final = fixate(scope)

        self.assertTrue(final[package['amba']])

    def test_optional_include2(self):
        package = Package('root')
        module_package(package, 'amba', depends = ['bad_module'])
        module_package(package, 'bad_module')

        def uart_trigger(scope, find_fn):
            opt = find_fn('uart.amba_pp')
            if opt.value(scope):
                return cut(scope, find_fn('amba'), BoolDom([True]))
            return cut(scope, find_fn('bad_module'), BoolDom([True]))

        module_package(package, 'uart', options = [Boolean('amba_pp')] , include_trigger=uart_trigger)

        scope = Scope()
        scope = add_many(scope, map(lambda s: package[s], ['uart', 'amba', 'bad_module']))

        self.assertRaises(CutConflictException, 
                cut_many, scope, [(package['uart'],       BoolDom([True])), 
                                  (package['bad_module'], BoolDom([False]))])

    def test_interface(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api')
        module_package(package, 'head_timer', implements=['timer_api'])

        scope = Scope()
        scope = add_many(scope, map(lambda s: package[s], ['timer_api', 'head_timer']))

        cut_many(scope, [(package['head_timer'], BoolDom([True]))])

        final = fixate(scope)

        self.assertEqual(final[package['timer_api']], Domain([package['head_timer']]))

    def test_interface2(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api')
        module_package(package, 'head_timer', implements=['timer_api'])
        module_package(package, 'timer_exmp', depends = ['timer_api'])

        scope = Scope()
        scope = add_many(scope, map(lambda s: package[s], ['timer_api', 'head_timer', 'timer_exmp']))

        cut_many(scope, [(package['timer_exmp'], BoolDom([True]))])

        final = fixate(scope)

        self.assertEqual(final[package['timer_api']], ModDom([package['head_timer']]))

    @unittest.expectedFailure 
    def test_options(self):
        timer_api = Interface("Timer api")
        head_timer = Module("Head timer", implements=timer_api, options = {'timer_nr' : 32, 'impl_name' : None})
        rt = Module("Hard realtime head timer", implements=timer_api, super=head_timer, options={'impl_name' : "rt timer"})

        scope = try_add_step(Scope(), rt)
        scope = try_add_step(scope, head_timer, options = {'timer_nr' : 64})

        self.assertEqual(rt.option_val(scope, 'timer_nr'),            64)
        self.assertEqual(rt.option_val(scope, 'impl_name'),            "rt timer")
        self.assertEqual(head_timer.option_val(scope, 'impl_name'), None)

    @unittest.expectedFailure 
    def test_options_error(self):
        timer = Module("Head timer", options = {'timer_nr' : 32})
        self.assertRaises(AttributeError, try_add_step, Scope(), timer, options = {'inobviously incorrect name' : 32 })

    @unittest.expectedFailure 
    def test_constraints(self):
        stack_lds = Module("stack", options = {'stack_sz' : 1024})
        tunings = [Tuning(stack_lds, None, lambda scope: ent.option_val(scope, 'stack_sz') > 4096)]

        thread_core = Module("thread_core", tunings=tunings)

        scope = try_add_step(Scope(), stack_lds)
        self.assertTrue(False != scope[stack_lds])
        scope = try_add_step(scope, thread_core)
        self.assertRaises(AttributeError, scope.__getitem__, thread_core)

    @unittest.expectedFailure 
    def test_constraints_unordered(self):
        stack_lds = Module("stack", options = {'stack_sz' : 8192})
        tunings = [Tuning(stack_lds, None, lambda scope: ent.option_val(scope, 'stack_sz') > 4096)]

        thread_core = Module("thread_core", tunings=tunings)

        scope = try_add_step(Scope(), thread_core)
        scope = try_add_step(scope, stack_lds)
        self.assertTrue(False != scope[thread_core])
        self.assertTrue(False != scope[stack_lds])

    def test_scope_pred(self):
        scope = Scope()
        self.assertTrue(scope != False)
        scope = Scope(scope)
        self.assertTrue(scope != False)


if __name__ == '__main__':
    unittest.main()
