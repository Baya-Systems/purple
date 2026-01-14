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

Initial approach is fully manual (here)
Will see which parts of it make sense to move to be part of Purple

Notes:
    only works if the entire history of the implementation-sim is available;
    cannot eg find a solution for the first 100 cycles then look for a solution for
    the next 100 keeping the same search history.  this is because some rule order
    options may have been ruled out during the search, which additional stimulus
    make possible/necessary

Status:
    fast to pass, slow to fail
    unuseably slow to fail with systematic rule order search
    just about OK with hash matching
    requirement for causality done
        cautious approach: allow input if any output is later
        more aggresive: allow input if all outputs are later
        either gives a big improvement in time-to-fail
    note the entire clocked sim is specific to rob
        because we're only using the purple clocked sim as a placeholder for an RTL EDA tool
    add a doc
    add a second implementation which stalls on repeated ID, no buffer
'''

from purple import StimulusIOTestbenchBase, StimulusInput, StimulusOutput
from rob_spec_test import ReOrderBufferSpec
from rob_implementation_test import Config, Types, Implementation_Testbench, RobImplSimulator
from cli import args

class Config(Config):
    suppress_implementation_checks = True
    ps_per_checksearch = (100 if args.quick else 1000) * 1000
    total_ps = (100 if args.quick else 10000) * 1000
    ps_to_bug_injection = 5500 * 1000
    num_packets_to_report = 16


class Rob_SpecChecker_Testbench(StimulusIOTestbenchBase):
    'spec (atomic-rule) testbench with stimulus/checking using stimulus-queues'
    new_req_a: StimulusInput[Types.RequesterPacket]
    new_req_b: StimulusInput[Types.RequesterPacket]
    req_to_completer: StimulusOutput[Types.CompleterPacket]
    comp_from_completer: StimulusInput[Types.CompleterPacket]
    comp_to_requester_a: StimulusOutput[Types.RequesterPacket]
    comp_to_requester_b: StimulusOutput[Types.RequesterPacket]

    dut: ReOrderBufferSpec[
        _.request_in_a << new_req_a.port_for_spec_input,
        _.request_in_b << new_req_b.port_for_spec_input,
        _.request_out >> req_to_completer.port_for_spec_output,
        _.completion_in << comp_from_completer.port_for_spec_input,
        _.completion_out_a >> comp_to_requester_a.port_for_spec_output,
        _.completion_out_b >> comp_to_requester_b.port_for_spec_output,
    ]

    def stimulus_input_mapping(self, implementation =  None):
        return (
            (getattr(implementation, 'req_out_a', None), self.new_req_a),
            (getattr(implementation, 'req_out_b', None), self.new_req_b),
            (getattr(implementation, 'comp_out', None), self.comp_from_completer),
        )

    def stimulus_output_mapping(self, implementation = None):
        return (
            (getattr(implementation, 'req_in', None), self.req_to_completer),
            (getattr(implementation, 'comp_in_a', None), self.comp_to_requester_a),
            (getattr(implementation, 'comp_in_b', None), self.comp_to_requester_b),
        )

    def copy_implementation_io(self, implementation, time_ps, inject_bug = False):
        # runs after every clock cycle
        sm = self.stimulus_input_mapping(implementation) + self.stimulus_output_mapping(implementation)
        bug = False
        for vr,sq in sm:
            PT = sq.param_entry_type
            if vr.valid and vr.ready:
                if inject_bug and not bug:
                    packet = PT(payload = vr.payload, txn_id = vr.txn_id ^ 1)
                    bug = True
                else:
                    packet = PT(payload = vr.payload, txn_id = vr.txn_id)
                sq.queue.push(packet, time_ps)
        return bug


class RobCheckerSimulator(RobImplSimulator):
    # extends clocked simulator to copy inputs and outputs after every cycle
    # and enables it to run the spec (atomic-rule) simulator as a tester
    def __init__(self, impl_random_seed = None):
        print('elaborating spec testbench')
        self.spec_testbench = Rob_SpecChecker_Testbench()

        print('elaborating implementation testbench')
        clks = dict(frequency_GHz = 1.0, name = 'clk')
        impl_testbench = Implementation_Testbench()

        print('making implementation simulator')
        super().__init__(impl_testbench, clks, random_seed = impl_random_seed)

    def run_one_step(self, final_time_ps, show_print, print_headers):
        while True:
            clock, clock_name = min(self.clocks)
            if clock.next_event_time_ps > final_time_ps:
                break
            self.time_ps = clock.next_event_time_ps
            self.spec_testbench.copy_implementation_io(self.system, self.time_ps)
            selected_rules = self.select_rules(clock, clock_name)
            clock.event(selected_rules, show_print, print_headers)
            yield

    def run_checking_simulation(self, total_ps, duration_ps):
        desired_stop_time_ps = 0
        check_state = None
        while True:
            print('** Running implementation testbench to get more stimulus **')
            desired_stop_time_ps += duration_ps
            self.run(desired_stop_time_ps - self.time_ps, show_print = False, print_headers = False)
            if self.time_ps >= total_ps:
                # this will mean no further StimulusQueueNeedsMoreData exceptions
                self.spec_testbench.finalise_all_stimulus()

            check_state = self.spec_testbench.checksearch(check_state)
            check_state.show('Search status with latest stimulus', self.time_ps, total_ps)

            if check_state.waiting_for_input():
                continue
            elif check_state.passed():
                print('Found a rule sequence')
                return True
            elif check_state.failed():
                print('Failed to find a rule sequence')
                self.spec_testbench.report_after_fail(Config.num_packets_to_report)
                return False
            else:
                assert False


sim = RobCheckerSimulator()
result = sim.run_checking_simulation(Config.total_ps, Config.ps_per_checksearch)
assert result


if not args.quick:
    print()
    print('Now run with bug injection')

    class BugInjectingSimulator(RobCheckerSimulator):
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
