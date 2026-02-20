'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Want to compare an atomic-rule and clocked implementation of the same thing

Well, want to verify the clocked using the atomic
This file is an alternative (simpler) clocked (RTL) implementation

A simple Re-order Buffer Structure

* Requests come in
* Their ID is extended (with 0) and they are sent to a completer
* The ROB blocks new requests
* The completer sends responses
* The ROB sends the responses to the requester and unblocks requests

Valid/ready flow control used throughout
All output ports are registered

Self-check uses same tuple-based history mechanism as spec-model
'''

from purple import Boolean, Model, Clock
from rob_implementation_test import (
    Config, Types,
    ValidReadyIn, ValidReadyOut, bind_valid_ready,
    Implementation_Testbench, RobImplSimulator
)
from cli import args


class SimpleReOrderBuffer(Model):
    current_req: Boolean = False
    current_comp: Boolean = False
    current_is_a: Boolean = False
    a_has_priority: Boolean = False

    request_in_a: ValidReadyIn[Types.Payload, Types.RequesterId]
    request_in_b: ValidReadyIn[Types.Payload, Types.RequesterId]
    request_out: ValidReadyOut[Types.Payload, Types.CompleterId]
    completion_in: ValidReadyIn[Types.Payload, Types.CompleterId]
    completion_out_a: ValidReadyOut[Types.Payload, Types.RequesterId]
    completion_out_b: ValidReadyOut[Types.Payload, Types.RequesterId]

    clk: Clock[on_clk_edge]

    def on_clk_edge(self):
        if self.current_req:
            self.request_in_a.ready = False
            self.request_in_b.ready = False
            vr = self.completion_out_a if self.current_is_a else self.completion_out_b

            if self.request_out.ready:
                self.request_out.valid = False

            if self.current_comp:
                # have sent completion, waiting for ready
                if vr.ready:
                    self.current_req = False
                    self.current_comp = False
                    vr.valid = False

            else:
                # waiting for completion
                if self.completion_in.valid:
                    if self.completion_in.ready:
                        self.current_comp = True
                        vr.valid = True
                        vr.payload = self.completion_in.payload
                        vr.txn_id = self.completion_in.txn_id
                        self.completion_in.ready = False
                    else:
                        self.completion_in.ready = True

        else:
            assert not self.current_comp
            # waiting for new request
            if self.a_has_priority:
                if not self.clk_capture_req(True):
                    self.clk_capture_req(False)
            else:
                if not self.clk_capture_req(False):
                    self.clk_capture_req(True)

    def clk_capture_req(self, a_not_b):
        vr = self.request_in_a if a_not_b else self.request_in_b
        if vr.valid:
            vr.ready = True
            self.request_out.valid = True
            self.request_out.payload = vr.payload
            self.request_out.txn_id = vr.txn_id
            self.current_req = True
            self.current_is_a = a_not_b
            self.a_has_priority = not a_not_b
            return True
        else:
            return False


class Simple_Implementation_Testbench(Implementation_Testbench):
    dut: SimpleReOrderBuffer[
        bind_valid_ready(_.request_in_a, req_out_a),
        bind_valid_ready(_.request_in_b, req_out_b),
        bind_valid_ready(req_in, _.request_out),
        bind_valid_ready(_.completion_in, comp_out),
        bind_valid_ready(comp_in_a, _.completion_out_a),
        bind_valid_ready(comp_in_b, _.completion_out_b),
    ]


# run simulation if imported as a top-level test
if __name__ == args.test_name + '_test':
    import random
    print('done import')
    tb = Simple_Implementation_Testbench()
    # elaboration takes a long time because the number of rules is huge
    print('done elaboration')
    seed = random.randrange(0x1_0000_0000)
#    seed = 3994852814
    sim = RobImplSimulator(tb, dict(frequency_GHz = 1.0, name = 'clk'), random_seed = seed)
    print('done building simulator, seed =', seed)
    n = 100 if args.quick else 100000
    sim.run(cycles_of_fastest_clock = n, print_headers = False)
