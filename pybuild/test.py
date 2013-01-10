
import unittest

from exception import *

from .. package import Package, obj_in_pkg
from scope   import Scope
from ops     import *

from option  import Boolean, List, Integer, String
from domain  import BoolDom, ListDom, IntegerDom, Domain, ModDom, StringDom

from module  import Module
from interface import Interface

def module_package(package, name, *args, **kargs):
    obj_in_pkg(Module, package, name, *args, **kargs)

def package_find(package, mod_name):
    return getattr(package, mod_name)

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
        scope = add_many(scope, map(lambda s: getattr(package, s), ['blck', 'stdio', 'fs', 'test', 'test2', 'test3']))

        scope = cut_many(scope, [(package.fs, BoolDom([True])), (package.test2, BoolDom([True]))])

        final = fixate(scope)
        
        self.assertEqual(final[package.blck],  BoolDom([True]))
        self.assertEqual(final[package.stdio], BoolDom([True]))
        self.assertEqual(final[package.fs],    BoolDom([True]))
        self.assertEqual(final[package.test],  BoolDom([True]))
        self.assertEqual(final[package.test2], BoolDom([True]))
        self.assertEqual(final[package.test3], BoolDom([False]))

    def test_depends_with_options(self):
        package = Package('root')
        module_package(package, 'stack', options = [Integer('stack_sz', domain = range(8192,1000000))])
        module_package(package, 'thread_core', depends = [ ('stack', {'stack_sz' : 16000}) ])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['stack', 'thread_core']))

        scope = cut_many(scope, [(package.stack, BoolDom([True])), (package.thread_core, BoolDom([True]))])

        final = fixate(scope)

        self.assertTrue(final[package.thread_core])
        self.assertTrue(final[package.stack])
        self.assertEqual(final[package.stack.stack_sz], Domain([16000]))

    def test_depends_with_list(self):
        package = Package('root')

        def incl_trigger(scope, find_fn):
            opt = find_fn('lds.sections')
            return cut(scope, opt, ListDom(['test']))

        module_package(package, 'lds', options = [List('sections')])
        module_package(package, 'stack_lds', depends = [ 'lds' ], include_trigger=incl_trigger)

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['lds', 'stack_lds']))

        scope = cut_many(scope, [(package.stack_lds, BoolDom([True]))])

        final = fixate(scope)

        self.assertTrue(final[package.lds])
        self.assertTrue(final[package.stack_lds])
        self.assertEqual(len(final[package.lds.sections]), 1)

    def test_depends_with_options2(self):
        package = Package('root')
        module_package(package, 'stack', options = [Integer('stack_sz', domain = range(8192,12000))])
        module_package(package, 'thread_core', depends = [ ('stack', {'stack_sz' : 16000}) ])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['stack', 'thread_core']))

        self.assertRaises(CutConflictException, cut, scope, package.thread_core, BoolDom([True]))

    def test_optional_include(self):
        package = Package('root')
        module_package(package, 'amba')

        def uart_trigger(scope, find_fn):
            opt = find_fn('uart.amba_pp')
            if opt.value(scope):
                return cut(scope, package.amba, BoolDom([True]))
            return scope

        module_package(package, 'uart', options = [Boolean('amba_pp')] , include_trigger=uart_trigger)
        
        scope = Scope()
        scope = add_many(scope, [package.uart, 
                         package.amba])
        scope = cut_many(scope, [(package.uart, BoolDom([True])), 
                                 (package.uart.amba_pp, BoolDom([True]))])

        self.assertTrue(scope != False)

        final = fixate(scope)

        self.assertTrue(final[package.amba])

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
        scope = add_many(scope, map(lambda s: getattr(package, s), ['uart', 'amba', 'bad_module']))

        scope = cut_many(scope, [(package.uart,       BoolDom([True])), 
                                 (package.bad_module, BoolDom([False]))])

        self.assertRaises(CutConflictException, fixate, scope)

    def test_interface(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api')
        module_package(package, 'head_timer', implements=['timer_api'])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['timer_api', 'head_timer']))

        cut_many(scope, [(package.head_timer, BoolDom([True]))])

        final = fixate(scope)

        self.assertEqual(final[package.timer_api], Domain([package.head_timer]))

    def test_interface2(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api')
        module_package(package, 'head_timer', implements=['timer_api'])
        module_package(package, 'timer_exmp', depends = ['timer_api'])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['timer_api', 'head_timer', 'timer_exmp']))

        cut_many(scope, [(package.timer_exmp, BoolDom([True]))])

        final = fixate(scope)

        self.assertEqual(final[package.timer_api], ModDom([package.head_timer]))

    def test_interface_default(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api', default = 'head_timer')
        module_package(package, 'head_timer', implements=['timer_api'])
        module_package(package, 'timer', implements=['timer_api'])
        module_package(package, 'timer_exmp', depends = ['timer_api'])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['timer_api', 'head_timer', 'timer', 'timer_exmp']))

        cut_many(scope, [(package.timer_exmp, BoolDom([True]))])

        final = fixate(scope)

        self.assertEqual(final[package.timer_api], ModDom([package.head_timer]))

    def test_interface_default2(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api', default = 'timer')
        module_package(package, 'head_timer', implements=['timer_api'])
        module_package(package, 'timer', implements=['timer_api'])
        module_package(package, 'timer_exmp', depends = ['timer_api'])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['timer_api', 'head_timer', 'timer', 'timer_exmp']))

        cut_many(scope, [(package.timer_exmp, BoolDom([True]))])

        final = fixate(scope)

        self.assertEqual(final[package.timer_api], ModDom([package.timer]))

    def test_interface_none(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'useless_api', default = 'big_module')
        module_package(package, 'big_module', implements=['useless_api'])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['useless_api', 'big_module']))
        
        cut_many(scope, [])

        final = fixate(scope)
    
        self.assertEqual(final[package.useless_api], ModDom([package.useless_api.def_impl]))
        self.assertEqual(final[package.big_module], BoolDom([False]))

    def test_moddom(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api')

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['timer_api']))

        self.assertRaises(CutConflictException, cut_many, scope, [(package.timer_api, BoolDom([True]))])

    def test_moddom2(self):
        package = Package('root')
        module_package(package, 'head_timer', implements=['timer_api'])
        module_package(package, 'timer', implements=['timer_api'])
        obj_in_pkg(Interface, package, 'timer_api')

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['timer_api', 'head_timer', 'timer']))

        cut_many(scope, [(package.timer_api, BoolDom([True]))])
        cut_many(scope, [(package.timer, BoolDom([False]))])

        self.assertEqual(scope[package.timer_api], ModDom([package.head_timer]))
                            

    def test_mandatory(self):
        package = Package('root')
        module_package(package, 'mod', mandatory = True)
        module_package(package, 'dep', depends = ['mod'])

        mod_lst = map(lambda s: getattr(package, s), ['mod', 'dep'])

        scope = Scope()
        scope = add_many(scope, mod_lst)

        scope = fix(scope, package.dep)

        final = fixate(scope)

        self.assertEqual(final[package.mod], BoolDom([True]))
        self.assertEqual(final[package.dep], BoolDom([False]))

    def test_mandatory2(self):
        package = Package('root')
        module_package(package, 'mod')
        module_package(package, 'dep', depends = ['mod'], mandatory = True)

        mod_lst = map(lambda s: getattr(package, s), ['mod', 'dep'])

        scope = Scope()
        scope = add_many(scope, mod_lst)

        scope = fix(scope, package.mod)

        final = fixate(scope)

        self.assertEqual(final[package.mod], BoolDom([True]))
        self.assertEqual(final[package.dep], BoolDom([True]))

    def test_interface_mandatory(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api', mandatory = True)

        mod_lst = map(lambda s: getattr(package, s), ['timer_api'])

        scope = Scope()
        self.assertRaises(CutConflictException, add_many, scope, mod_lst)

    def test_interface_mandatory2(self):
        package = Package('root')
        obj_in_pkg(Interface, package, 'timer_api', mandatory = True)
        module_package(package, 'timer', implements=['timer_api'])

        mod_lst = map(lambda s: getattr(package, s), ['timer_api', 'timer'])

        scope = Scope()
        scope = add_many(scope, mod_lst)

        self.assertEqual(scope[package.timer_api], ModDom([package.timer]))

    def test_options(self):
        package = Package('root')
        module_package(package, 'timer', options = [
            Integer('timer_nr', default = 32),
            Integer('id', default = 1)])

        module_package(package, 'super_timer', super = 'timer', options = [
            Integer('id', default = 2)])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['super_timer', 'timer']))
    
        cut_many(scope, [(package.super_timer.timer_nr, IntegerDom([64])),
            (package.super_timer, BoolDom([True]))])

        final = fixate(scope)

        self.assertEqual(package.super_timer.timer_nr.qualified_name(), 'super_timer.timer_nr')
        #self.assertEqual(final[package.timer.id], IntegerDom([1]))
        self.assertEqual(final[package.super_timer.id], IntegerDom([2]))
        #self.assertEqual(final[package.timer.timer_nr], IntegerDom([32]))
        self.assertEqual(final[package.super_timer.timer_nr], IntegerDom([64]))

    def test_string_opt(self):
        package = Package('root')
        module_package(package, 'hello', options = [
            String('call', default = 'Me'),
            ])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['hello']))

        cut_many(scope, [(package.hello, BoolDom([True]))])

        final = fixate(scope)
    
        self.assertEqual(final[package.hello.call], StringDom(['Me']))
    
    def test_string_opt2(self):
        package = Package('root')
        module_package(package, 'hello', options = [
            String('call', default = 'Me'),
            ])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['hello']))

        cut_many(scope, [(package.hello, BoolDom([True])), 
            (package.hello.call, StringDom(['You']))])

        final = fixate(scope)
    
        self.assertEqual(final[package.hello.call], StringDom(['You']))
    
    def test_string_opt3(self):
        package = Package('root')
        module_package(package, 'hello', options = [
            String('call', default = 'Me'),
            ])

        scope = Scope()
        scope = add_many(scope, map(lambda s: getattr(package, s), ['hello']))

        self.assertRaises(CutConflictException, 
            cut_many, scope, [(package.hello, BoolDom([True])), 
            (package.hello.call, StringDom(['You'])),
            (package.hello.call, StringDom(['Other']))])

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
