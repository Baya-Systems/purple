'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Want to compare an atomic-rule and clocked implementation of the same thing

Well, want to verify the clocked using the atomic
This file is the testbench containing both the spec and implementation
And comparison between them

The implementation testbench is run, capturing the inputs and outputs of the implementation-DUT
A simple testbench for the spec is implemented which
    uses the implementation-DUT inputs as inputs to the spec-DUT
    checks whether any sequence of spec-DUT rules can create the implementation-GUT outputs

This file is for a second variant of the implementation, tested against the same
specification model.
'''

from purple import StimulusIOTestbenchBase, StimulusInput, StimulusOutput
from rob_spec_test import ReOrderBufferSpec
from rob_simple_impl_test import Config, Types, Simple_Implementation_Testbench, RobImplSimulator
from rob_checker_test import RobCheckerSimulator, Rob_SpecChecker_Testbench
from cli import args

class Config(Config):
    suppress_implementation_checks = True
    ps_per_checksearch = (100 if args.quick else 1000) * 1000
    total_ps = (100 if args.quick else 10000) * 1000
    ps_to_bug_injection = 5500 * 1000
    num_packets_to_report = 16


class SimpleRobCheckerSimulator(RobCheckerSimulator):
    # extends clocked simulator to copy inputs and outputs after every cycle
    # and enables it to run the spec (atomic-rule) simulator as a tester
    def __init__(self, impl_random_seed = None):
        print('elaborating spec testbench')
        self.spec_testbench = Rob_SpecChecker_Testbench()

        print('elaborating implementation testbench')
        clks = dict(frequency_GHz = 1.0, name = 'clk')
        impl_testbench = Simple_Implementation_Testbench()

        print('making implementation simulator')
        RobImplSimulator.__init__(self, impl_testbench, clks, random_seed = impl_random_seed)


if __name__ == args.test_name + '_test':
    seed = None
#    seed = 190827057014494
    sim = SimpleRobCheckerSimulator(impl_random_seed = seed)
    result = sim.run_checking_simulation(Config.total_ps, Config.ps_per_checksearch)
    assert result, f'failed with seed = {sim.seed}'

    if not args.quick:
        print()
        print('Now run with bug injection')

        class BugInjectingSimulator(SimpleRobCheckerSimulator):
            def __init__(self, *a, **ka):
                super().__init__(*a, **ka)
                self.bug_injected = False

            def run_one_step(self, final_time_ps, show_print, print_headers):
                while True:
                    clock, clock_name = min(self.clocks)
                    if clock.next_event_time_ps > final_time_ps:
                        break
                    self.time_ps = clock.next_event_time_ps
                    inject_bug = (not self.bug_injected) and self.time_ps > Config.ps_to_bug_injection
                    self.bug_injected = \
                        self.spec_testbench.copy_implementation_io(self.system, self.time_ps, inject_bug)
                    selected_rules = self.select_rules(clock, clock_name)
                    clock.event(selected_rules, show_print, print_headers)
                    yield

        sim2 = BugInjectingSimulator()
        result = sim2.run_checking_simulation(Config.total_ps, Config.ps_per_checksearch)
        assert not result
