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

import inspect

from . import rule


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
        return cls(client_refs)

    def elaborate(self, owner):
        '''create a useable clock object with a list of rule objects

        must be called after state elaboration
        flag any downstream clocks as not directly visible from top-level
        reject rules with parameters

        client-references may be one of
            purple-type-proxy with hierarchical name of function object
            purple-type-proxy with hierarchical name of clock object
            function object
        '''
        rules = []
        for cref in self.client_refs:
            if inspect.isfunction(cref):
                rule_name = cref.__name__
                rule_owner = owner
            else:
                client = owner
                for n in cref.name:
                    rule_owner = client
                    try:
                        client = getattr(client, n)
                    except AttributeError:
                        client = client._dp_clocks[n]
                if isinstance(client, Clock):
                    client.driven_by_another_clock = True
                    rules.extend(client.rules)
                    continue
                else:
                    rule_name = cref.name[-1]

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
        update next-event time of clock object
        '''
        assert not self.driven_by_another_clock

        successful = []
        for r in selected_rules:
            inv = r.invoke(check = True, print_headers = False, show_print = False)
            if not inv.guarded:
                inv.revert_state()
                successful.append(inv)

        for inv in successful:
            inv.apply_state()
            if show_print:
                inv.produce_printout(print_headers)

        self.next_event_time_ps += self.period_ps
        self.num_events += 1

    def __lt__(self, other):
        # allows use of min() to find next clock that fires
        return self.next_event_time_ps < other.next_event_time_ps
