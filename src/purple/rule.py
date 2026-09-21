'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple state-update rules
'''

from . import common
import annotationlib


class Rule:
    def __init__(self, component, method, params):
        self.component = component
        self.method_name = method.__name__
        self.top_component = getattr(component, '_dp_top_component', None)
        self.method = method
        self.params = params

    def __str__(self):
        cmp_name = '.'.join(self.component.name)
        params = ', '.join(f'{n}={v}' for n,v in self.params.items())
        return f'{cmp_name}.{self.method_name}({params})'

    def invoke(self, check = True, print_headers = True, show_print = True):
        with Invocation(self) as invocation:
            self.method(**self.params)
        if check and invocation.exc_type is not None:
            raise invocation.exc_value
        if show_print and not invocation.guarded:
            invocation.produce_printout(headers = print_headers)
        return invocation


class Invocation:
    '''Stores data about a Rule invocation: success/failure and the system state before and after
    '''
    def __init__(self, rule):
        self.rule = rule
        self.top_component = rule.top_component
        self.exc_type = None
        self.exc_value = None
        self.guarded = False
        self.state_changes = dict() # (component_name,leaf_name):LeafStateChange
        self.printout = []

    def __enter__(self):
        self.top_component._dp_raw_setattr('_dp_current_invocation', self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            # FIXME
            # cannot revert state if the exception was caused by an unhashable leaf
            # so should detect such cases (they are fatal and make a mess for the user)
            self.revert_state()
            if exc_type is common.GuardFailed:
                self.guarded = True
            else:
                self.exc_type = exc_type
                self.exc_value = exc_value
        self.top_component._dp_raw_setattr('_dp_current_invocation', None)
        return True

    def leaf_state_change(self, change):
        update_key = change.component.name, change.leaf_name
        repeated_update = self.state_changes.get(update_key, None)
        change.apply()
        if repeated_update is not None:
            change.value_before = repeated_update.value_before
        self.state_changes[update_key] = change

    def revert_state(self):
        for change in self.state_changes.values():
            change.revert()

    def apply_state(self):
        for change in self.state_changes.values():
            change.apply()

    def print(self, args, kwargs):
        self.printout.append((args, kwargs))

    def produce_printout(self, headers, file = None):
        for args, kwargs in self.printout:
            if file and 'file' not in kwargs:
                kwargs['file'] = file
            if headers:
                args = (self.rule, '::', *args)
            print(*args, **kwargs)


def construct_all(instance, method_name):
    ''' make a list of Rule objects from a method name, one per parameter set

    instance may be a class (for declaration-time testing) or an object being elaborated
    '''
    the_method = getattr(instance, method_name)
    annots = annotationlib.get_annotations(the_method)
    a_list = [a for a in annots.items() if a[0] != 'return']
    return [Rule(instance, the_method, pd) for pd in construct_all_recursive(a_list)]

def construct_all_recursive(param_items):
    if not param_items:
        yield dict()
    else:
        (first_pname, first_ptype),others = param_items[0], param_items[1:]
        for first_value in first_ptype._dp_all_possible_values():
            first_dict = {first_pname:first_value}
            for others_dict in construct_all_recursive(others):
                yield dict(**first_dict, **others_dict)
