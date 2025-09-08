'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

simulator (base) classes
- atomic rules, rule selected randomly (by default)
- clocked

FIXME:
    - save/restore
    - auto switch to debug on exception, either post-mortem or whole rule
    - interact
        - choose next rule
        - view/modify state
        - go backwards (also for clocked)
    - code coverage
    - state coverage
'''

import random


class SimulatorBase:
    def __init__(self, system):
        self.system = system

    def interact(self):
        assert False, 'interactive simulator not yet implemented'

    def save(self, destination):
        assert False, 'saving simulator state not yet implemented'

    def restore(self, source):
        assert False, 'restoring simulator state not yet implemented'


class AtomicRuleSimulator(SimulatorBase):
    def __init__(self, system, random_seed = None):
        super().__init__(system)
        self.num_invocations = 0
        self.all_rules = tuple(self.system.find_rule())
        self.rule_pool = self.make_rule_pool()
        self.seed = random.getrandbits(48) if random_seed is None else random_seed
        self.rand_gen = random.Random(self.seed)
        self.deadlocked = False

    def make_rule_pool(self):
        # redefine in subclass eg to group rules into priorities
        return self.all_rules

    def choose_rule(self):
        # redefine in subclass to do something other than uniform rule selection
        return self.rand_gen.choice(self.rule_pool)

    def default_num_guards_before_exhaustive(self):
        # redefine in subclass if required
        return len(self.rule_pool) // 2

    def run(self, num_invocations,
        show_print = True,
        print_headers = True,
        num_guards_before_exhaustive = None,
    ):
        final_num_invocations = self.num_invocations + num_invocations
        if num_guards_before_exhaustive is None:
            num_guards_before_exhaustive = self.default_num_guards_before_exhaustive()

        while self.num_invocations < final_num_invocations:
            # try to find a rule that can run
            for _ in range(num_guards_before_exhaustive):
                result = self.choose_rule().invoke(
                    check = True,
                    print_headers = print_headers,
                    show_print = show_print,
                )
                if not result.guarded:
                    break

            # failed guesswork; search exhaustively and select one at random
            if result.guarded:
                invokable = []
                for rule in self.all_rules:
                    result = rule.invoke(
                        check = True,
                        print_headers = False,
                        show_print = False,
                    )
                    if not result.guarded:
                        invokable.append(result)
                        result.revert_state()

                if invokable:
                    result = self.rand_gen.choice(invokable)
                    result.apply_state()
                    if show_print:
                        result.produce_printout(print_headers)
                else:
                    print('System Deadlock')
                    self.deadlocked = True
                    break

            self.num_invocations += 1


class ClockedSimulator(SimulatorBase):
    def __init__(self, system, *clock_inputs):
        super().__init__(system)
        self.time_ps = 0

        # clock_inputs is a tuple of dicts:
        #   frequency_GHz or period_ps
        #   phase_ps (optional)
        #   name (optional, for finding clocks)
        #   component_name (optional, for finding clocks)

        self.clocks = []
        self.fastest_clock = None
        for clock_params in clock_inputs:
            clock_name = clock_params.get('name', '')

            component_name = clock_params.get('component_name', None)
            if component_name is None:
                component = None
            else:
                component = system
                while True:
                    assert component_name[0] == component.name[-1]
                    print
                    component_name = component_name[1:]
                    if not component_name:
                        break
                    component = getattr(component, component_name[0])

            for clock in system.find_clock(component = component, name = clock_name):
                self.clocks.append(clock)
                frequency_GHz = clock_params.get('frequency_GHz', None)
                if frequency_GHz is None:
                    period_ps = clock_params['period_ps']
                else:
                    period_ps = int(0.5 + 1000.0 / frequency_GHz)
                phase_ps = clock_params.get('phase_ps', 0)
                clock.set_period_ps(period_ps, phase_ps)
                if self.fastest_clock is None or period_ps < self.fastest_clock.period_ps:
                    self.fastest_clock = clock

    def sim_end_time(self, duration_ps = None, cycles = None, cycles_of_fastest_clock = None):
        if duration_ps is None:
            if cycles is None:
                duration_ps = int((0.5 + cycles_of_fastest_clock) * self.fastest_clock.period_ps)
            else:
                duration_ps = int((0.5 + cycles) * self.clocks[0].period_ps)
        return self.time_ps + duration_ps

    def run_one_step(self, final_time_ps, show_print, print_headers):
        while True:
            clock = min(self.clocks)
            if clock.next_event_time_ps >= final_time_ps:
                break
            self.time_ps = clock.next_event_time_ps
            clock.event(show_print, print_headers)
            yield

    def run(self,
        duration_ps = None,
        cycles = None,
        cycles_of_fastest_clock = None,
        show_print = True,
        print_headers = True,
    ):
        final_time_ps = self.sim_end_time(duration_ps, cycles, cycles_of_fastest_clock)
        for step in self.run_one_step(final_time_ps, show_print, print_headers):
            pass
