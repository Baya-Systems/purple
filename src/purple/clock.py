''''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple Clock type


Objects of type Clock are recorded in declared Model subclasses
These only have references to the clock's clients
A client reference may point to another clock, or to a rule

On elaboration, a new object of type Clock is created which also
contains the actual client objects (rules) sensitive to the clock
'''

import annotationlib
import inspect

from . import common, rule


class Clock:
    def __init__(self, client_refs, rules = [], elaborated = False):
        self.client_refs = client_refs
        self.driven_by_another_clock = False
        self.next_event_time_ps = 0
        self.num_events = 0
        self.rules = rules
        if elaborated:
            rule_methods = set(r.method for r in rules)
            self.rules_by_method = {m:[r for r in rules if r.method is m] for m in rule_methods}

    def __class_getitem__(cls, client_refs):
        # called on declaration
        if not isinstance(client_refs, tuple):
            client_refs = (client_refs,)
        return cls(tuple(client_refs))

    def elaborate(self, owner):
        '''create a useable clock object with a list of rule objects

        must be called after state elaboration
        flag any downstream clocks as not directly visible from top-level
        reject rules with parameters

        client-references may be one of
            purple-type-proxy with hierarchical name of function object
            purple-type-proxy with hierarchical name of clock object
            forward-reference to something not yet declared in some base class
            function object
        '''
        rules = []
        for cref in self.client_refs:
            if inspect.isfunction(cref):
                rule_name = cref.__name__
                rule_owner = owner
            else:
                if isinstance(cref, annotationlib.ForwardRef):
                    # possible eg if an abstract base class declared a clock method
                    dotted_name = cref.evaluate(format = annotationlib.Format.STRING)
                    name = dotted_name.split('.')
                else:
                    # cref should be a proxy object
                    name = cref.name

                # climb up the hierarchical tree to get the the driven clock or rule-method
                rule_owner = owner
                for name_element in name[:-1]:
                    rule_owner = getattr(rule_owner, name_element)

                if the_clock := rule_owner._dp_clocks.get(name[-1], None):
                    the_clock.driven_by_another_clock = True
                    rules.extend(the_clock.rules)
                    continue
                else:
                    rule_name = name[-1]

            rules.extend(rule.construct_all(rule_owner, rule_name))

        return type(self)(self.client_refs, rules, elaborated = True)

    def set_period_ps(self, period_ps, phase_ps = 0):
        self.period_ps = period_ps
        self.next_event_time_ps += phase_ps

    def event(self, selected_rules, show_print = True, print_headers = True):
        '''clock event

        invoke all selected bound rules
            revert system state after each one so they are all concurrent
        re-apply all system state changes
            merge first to support special leaf types that allow concurrent changes
            this can cause a guard to fail, in which case all rules touching the
                leaf must be assumed guarded, and all their updates suppressed
        update next-event time of clock object
        '''
        assert not self.driven_by_another_clock

        successful = set()
        for r in selected_rules:
            inv = r.invoke(check = True, print_headers = False, show_print = False)
            if not inv.guarded:
                inv.revert_state()
                successful.add(inv)

        merged_invocation = rule.Invocation(None)
        merged_state_changes = merged_invocation.state_changes
        merges_to_check = set()
        for inv in successful:
            for update_key,lsc in inv.state_changes.items():
                concurrent_update = merged_state_changes.get(update_key, None)
                if concurrent_update is None:
                    merged_state_changes[update_key] = lsc
                else:
                    concurrent_update.merge_concurrent_rules(lsc)
                    merged_state_changes[update_key] = concurrent_update
                    merges_to_check.add(update_key)

        unsuccessful = set()
        for update_key in merges_to_check:
            try:
                merged_state_changes[update_key].post_merge_check()
            except common.GuardFailed:
                # some merge from multiple concurrent rules caused a guard
                # so remove all changes from anything that was touched by any
                # of those rules
                for inv in successful:
                    if update_key in inv.state_changes:
                        unsuccessful.add(inv)

        for inv in unsuccessful:
            successful.remove(inv)
            for update_key in inv.state_changes:
                merged_state_changes.pop(update_key, None)

        for inv in successful:
            merged_invocation.printout += inv.printout

        merged_invocation.apply_state()
        if show_print:
            merged_invocation.produce_printout(print_headers)

        self.next_event_time_ps += self.period_ps
        self.num_events += 1

    def __lt__(self, other):
        # allows use of min() to find next clock that fires
        return self.next_event_time_ps < other.next_event_time_ps
