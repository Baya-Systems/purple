'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Want to compare an atomic-rule and clocked implementation of the same thing

Well, want to verify the clocked using the atomic
This file is the clocked (RTL) implementation

A simple Re-order Buffer Structure

* Requests come in
* Their ID is extended and they are sent to a completer
* The completer sends responses
* The ROB sends the responses to the requester in order depending on the original ID
* The selection of completer ID is non-architectural (many different implementations are acceptable)

Valid/ready flow control used throughout
All output ports are registered
Similar linked-list design to the spec model
Free-list and per-ID list are maintained instead of searching

Self-check uses same tuple-based history mechanism as spec-model

Status:
    RTL re-order buffer written and passing dedicated test in this file

Next
    Could add a simplified alternative RTL which blocks on ID collisions, see if the
    same checking with same spec-model works out of the box
'''

from purple import (
    Integer, ModuloInteger, Boolean, Enumeration,
    Model, Record, Generic, Port, Clock, Registered_Output_Port,
    ClockedSimulator, Tuple,
)
from rob_spec_test import Config, Types
from cli import args
import enum

class Config(Config):
    pr_new_req = 0.3
    pr_accept_req = 0.5
    pr_comp = 0.3
    pr_accept_comp = 0.5
    suppress_implementation_checks = False


@Generic
def ValidReadyIn(payload_type, id_type):
    class ValidReady_wrapper(Model):
        payload: Port[payload_type]
        txn_id: Port[id_type]
        valid: Port[Boolean]
        ready: Registered_Output_Port[Boolean, False]
    return ValidReady_wrapper

@Generic
def ValidReadyOut(payload_type, id_type):
    class ValidReady_wrapper(Model):
        payload: Registered_Output_Port[payload_type, 0]
        txn_id: Registered_Output_Port[id_type, 0]
        valid: Registered_Output_Port[Boolean, False]
        ready: Port[Boolean]
    return ValidReady_wrapper

def bind_valid_ready(vr_in, vr_out):
    vr_in.valid << vr_out.valid
    vr_in.payload << vr_out.payload
    vr_in.txn_id << vr_out.txn_id
    vr_in.ready >> vr_out.ready


ContextNumber = Integer[Config.num_contexts]

class TxnContext(Record):
    payload: Types.Payload
    source_id: Types.RequesterId
    source_is_a: Boolean

    in_resp_queue: Boolean
    resp_valid: Boolean
    oldest: Boolean

    # linked-list for ordering same-id transactions
    next_valid: Boolean
    next: ContextNumber


class ReOrderBuffer(Model):
    txn_queue: Config.num_contexts * TxnContext = [dict(
            in_resp_queue = False,
            next_valid = (i != Config.num_contexts - 1),
            next = ((i + 1) % Config.num_contexts),
        ) for i in range(Config.num_contexts)
    ]
    # possible transaction-context states
    # - in the linked-list of free contexts
    # - in the linked-list of req contexts, waiting to be sent to completer in original order
    # - in_resp_queue: in a linked-list-per-ID, with one of the follwing sub-states
    #   - waiting for response from completer
    #   - has response, waiting for older transactions with same original ID to be completed
    #   - has response and oldest for its original ID, waiting to win arbitration onto resp-out
    any_free_tq: Boolean = True
    two_free_tq: Boolean = (Config.num_contexts >= 2)
    first_free_tq: ContextNumber = 0
    last_req_from_a: Boolean = True
    any_req_tq: Boolean = False
    oldest_req_tq: ContextNumber
    newest_req_tq: ContextNumber
    round_robin_start: ModuloInteger[2**Config.source_id_width] = 0

    request_in_a: ValidReadyIn[Types.Payload, Types.RequesterId]
    request_in_b: ValidReadyIn[Types.Payload, Types.RequesterId]
    request_out: ValidReadyOut[Types.Payload, Types.CompleterId]
    completion_in: ValidReadyIn[Types.Payload, Types.CompleterId]
    completion_out_a: ValidReadyOut[Types.Payload, Types.RequesterId]
    completion_out_b: ValidReadyOut[Types.Payload, Types.RequesterId]

    clk: Clock[on_clk_edge]

    def on_clk_edge(self):
        # single rule, so that state updates become visible immediately in a defined order
        # can capture 2 requests/send 2 completions in the same cycle
        # can send 1 request/capture 1 completion in a cycle
        returned_tq_a = self.clk_send_comp_to_requester(True, self.completion_out_a)
        returned_tq_b = self.clk_send_comp_to_requester(False, self.completion_out_b)
        self.clk_capture_completion(self.completion_in)
        self.clk_send_req_to_completer(self.request_out)
        if self.last_req_from_a:
            self.clk_capture_req(False, self.request_in_b)
            self.clk_capture_req(True, self.request_in_a)
        else:
            self.clk_capture_req(True, self.request_in_a)
            self.clk_capture_req(False, self.request_in_b)

        # free-queue is popped by capture-req
        # free-queue is not pushed by send-comp, so that capture-req cannot use
        #   contexts released in the same cycle
        # that pushing happens here
        # capture-req pops from free-queue so here it is in a clean state and can be modified again
        def recover_context(returned_tq):
            if returned_tq is not None:
                tq = self.txn_queue[returned_tq]
                tq.next = self.first_free_tq
                tq.next_valid = self.any_free_tq
                self.two_free_tq = self.any_free_tq
                self.any_free_tq = True
                self.first_free_tq = returned_tq

        recover_context(returned_tq_a)
        recover_context(returned_tq_b)

        self.completion_in.ready = True
        if self.last_req_from_a:
            self.request_in_b.ready = self.any_free_tq
            self.request_in_a.ready = self.two_free_tq
        else:
            self.request_in_a.ready = self.any_free_tq
            self.request_in_b.ready = self.two_free_tq

    def clk_capture_req(self, source_is_a, vr):
        if (not vr.ready) or (not vr.valid):
            return

        assert self.any_free_tq
        tq_id = self.first_free_tq
        tq = self.txn_queue[tq_id]

        if tq.next_valid:
            self.first_free_tq = tq.next
            self.two_free_tq = self.txn_queue[tq.next].next_valid
        else:
            assert not self.two_free_tq
            self.any_free_tq = False

        tq.source_is_a = source_is_a
        tq.payload = vr.payload
        tq.source_id = vr.txn_id
        tq.resp_valid = False

        if self.any_req_tq:
            newest_req = self.txn_queue[self.newest_req_tq]
            newest_req.next_valid = True
            newest_req.next = tq_id
        else:
            self.oldest_req_tq = tq_id
        self.newest_req_tq = tq_id
        self.any_req_tq = True
        tq.next_valid = False

        self.last_req_from_a = source_is_a

    def clk_send_req_to_completer(self, vr):
        if vr.valid and not vr.ready:
            return

        if not self.any_req_tq:
            vr.valid = False
            return
        tq_id = self.oldest_req_tq
        tq = self.txn_queue[tq_id]

        # send oldest request to completer
        vr.valid = True
        vr.payload = tq.payload
        vr.txn_id = (tq_id << Config.source_id_width) | tq.source_id

        # advance req queue to next-oldest request, if any
        if tq.next_valid:
            self.oldest_req_tq = tq.next
        else:
            self.any_req_tq = False

        # move request to resp queue
        try:
            previous = next(t for t in self.txn_queue \
                if t.in_resp_queue and t.source_id == tq.source_id and not t.next_valid)
            previous.next = tq_id
            previous.next_valid = True
            tq.oldest = False
        except StopIteration:
            tq.oldest = True
        tq.in_resp_queue = True
        tq.resp_valid = False
        tq.next_valid = False

    def clk_capture_completion(self, vr):
        if (not vr.ready) or (not vr.valid):
            return

        tq_id = vr.txn_id >> Config.source_id_width
        tq = self.txn_queue[tq_id]
        assert tq.source_id == vr.txn_id - (tq_id << Config.source_id_width)
        assert not tq.resp_valid

        tq.resp_valid = True
        tq.payload = vr.payload

    def clk_send_comp_to_requester(self, source_is_a, vr):
        if vr.valid and not vr.ready:
            return None

        candidates = [(i,t) for i,t in enumerate(self.txn_queue) if
            t.in_resp_queue and t.source_is_a == source_is_a and t.resp_valid and t.oldest
        ]

        if not candidates:
            vr.valid = False
            return None

        tq_id,tq = min(candidates, key = self.arbitrate)
        self.round_robin_start = tq_id + 1

        # send response to requester
        vr.valid = True
        vr.txn_id = tq.source_id
        vr.payload = tq.payload

        # advance per-ID queue
        if tq.next_valid:
            self.txn_queue[tq.next].oldest = True

        # return context to free queue
        tq.in_resp_queue = False
        return tq_id

    def arbitrate(self, tqid_and_tq):
        # modulo operations, result is in 0 to max-source-id
        return -(self.round_robin_start - tqid_and_tq[1].source_id)


TxnState = enum.Enum('Txn', 'ReqInDut ReqInCompleter CompInDut CompInRequester')
# new request is created, put into DUT and stored in requester-side history
#       only source-id, req-payload, source-is-a
# request is received from DUT by completer process (req-in-completer)
#       check unique-ID
#       stored in completer history: source-id, dest-id req-payload
# completion is created, put into DUT and completer history updated with comp-payload
# completion is received from DUT by requester process, matched to requester history
#       and matched to completer history by source-id and req-payload and comp-payload
#       this is not fully unambiguous but doesn't matter
#       requester state goes to comp-in-requester
# completer checks in requester history one cycle later and deletes its (first) match

class TxnTracker(Record):
    source_id: Integer[...]
    dest_id: Integer[...]
    source_is_a: Boolean
    req_payload: Integer[...]
    comp_payload: Integer[...]
    state: Enumeration[TxnState]

def search_history(history, filter):
    return [(i,t) for i,t in enumerate(history) if filter(t)]

def purge_history(history, filter):
    return tuple(t for t in history if not filter(t))

class Implementation_Testbench(Model):
    requester_a_history: Tuple[TxnTracker]
    requester_b_history: Tuple[TxnTracker]
    completer_history: Tuple[TxnTracker]

    req_out_a: ValidReadyOut[Types.Payload, Types.RequesterId]
    req_out_b: ValidReadyOut[Types.Payload, Types.RequesterId]
    req_in: ValidReadyIn[Types.Payload, Types.CompleterId]
    comp_out: ValidReadyOut[Types.Payload, Types.CompleterId]
    comp_in_a: ValidReadyIn[Types.Payload, Types.RequesterId]
    comp_in_b: ValidReadyIn[Types.Payload, Types.RequesterId]

    dut: ReOrderBuffer[
        bind_valid_ready(_.request_in_a, req_out_a),
        bind_valid_ready(_.request_in_b, req_out_b),
        bind_valid_ready(req_in, _.request_out),
        bind_valid_ready(_.completion_in, comp_out),
        bind_valid_ready(comp_in_a, _.completion_out_a),
        bind_valid_ready(comp_in_b, _.completion_out_b),
    ]

    clk: Clock[requester_a_clk, requester_b_clk, completer_clk, dut.clk]

    def requester_a_clk(self,
        set_req_valid: Boolean,
        req_payload: Types.Payload,
        req_id: Types.RequesterId,
        set_comp_ready: Boolean,
    ):
        self.requester_clk(True, set_req_valid, req_payload, req_id, set_comp_ready)

    def requester_b_clk(self,
        set_req_valid: Boolean,
        req_payload: Types.Payload,
        req_id: Types.RequesterId,
        set_comp_ready: Boolean,
    ):
        self.requester_clk(False, set_req_valid, req_payload, req_id, set_comp_ready)

    def purged_completer(self):
        # return a list of all completer history that is to be deleted, so it can be ignored
        to_purge = []
        for req_history in self.requester_a_history, self.requester_b_history:
            tr = next((t for t in req_history if t.state is TxnState.CompInRequester), None)
            if tr:
                # delete exactly one thing from completer-history
                to_purge.append(next(t for t in self.completer_history if
                    t.state is TxnState.CompInDut and
                    t.dest_id == tr.dest_id and
                    t.req_payload == tr.req_payload and
                    t.comp_payload == tr.comp_payload and
                    t not in to_purge
                ))
        return purge_history(self.completer_history, (lambda t: t in to_purge))

    def requester_clk(self, source_is_a, set_req_valid, req_payload, req_id, set_comp_ready):
        p = 'A' if source_is_a else 'B'

        if source_is_a:
            def history(new_history = None):
                if new_history is not None:
                    self.requester_a_history = new_history
                return self.requester_a_history
        else:
            def history(new_history = None):
                if new_history is not None:
                    self.requester_b_history = new_history
                return self.requester_b_history

        # need to avoid hitting any "dead" completer records which are going to be purged
        # run this before any changes to the local history
        completer_history = self.purged_completer()

        # remove complete transactions, one cycle delayed so completer process can use them to purge
        new_history = purge_history(history(), (lambda t: t.state is TxnState.CompInRequester))
        history(new_history)

        # receive completions and check ordering
        vr = self.comp_in_a if source_is_a else self.comp_in_b
        if vr.valid and vr.ready:
            # find the oldest transaction with matching requester-side ID
            all_txns = search_history(history(), (lambda t: t.source_id == vr.txn_id))
            idx,txn = all_txns[0]

            # find the destination ID from the completer history
            def matcher(t):
                return \
                    t.state is TxnState.CompInDut and \
                    t.source_id == vr.txn_id and \
                    t.comp_payload == vr.payload and \
                    t.req_payload == txn.req_payload
            txns_at_completer = search_history(completer_history, matcher)
            # it is possible that the same search happens for both requester ports in the same cycle
            # in which case the length should be 2 and the ports must take different values
            # we cannot tell which was which if source-ID, req-payload and comp-payload all match
            if len(txns_at_completer) == 2:
                txn_at_completer = txns_at_completer[0 if source_is_a else 1][1]
            else:
                txn_at_completer = txns_at_completer[0][1]
            history().replace(idx, TxnTracker(
                source_id = txn.source_id,
                dest_id = txn_at_completer.dest_id,
                source_is_a = source_is_a,
                req_payload = txn.req_payload,
                comp_payload = vr.payload,
                state = TxnState.CompInRequester,
            ))

            self.print(f'\t\t\t\t\t\t\t\t\t\t\t\tRequester {p} completion: payload={vr.payload} txn_id={vr.txn_id}')

        # inject new requests
        vr = self.req_out_a if source_is_a else self.req_out_b
        if vr.ready or not vr.valid:
            if set_req_valid:
                vr.payload = req_payload
                vr.txn_id = req_id
                self.print(f'Requester {p} request: payload={req_payload} txn_id={req_id}')
                history().append(TxnTracker(
                    source_id = req_id,
                    source_is_a = source_is_a,
                    req_payload = req_payload,
                    state = TxnState.ReqInDut,
                ))
            vr.valid = set_req_valid

        # set ready signals for next clock cycle
        if source_is_a:
            self.comp_in_a.ready = set_comp_ready
        else:
            self.comp_in_b.ready = set_comp_ready

    def completer_clk(self,
        set_comp_valid: Boolean,
        comp_index: Types.CompleterId,
        comp_payload: Types.Payload,
        set_req_ready: Boolean,
    ):
        def history(new_history = None):
            if new_history is not None:
                self.completer_history = new_history
            return self.completer_history

        # remove finished transactions from history
        new_history = self.purged_completer()
        history(new_history)

        # send completions, possibly out of order
        vr = self.comp_out
        if vr.ready or not vr.valid:
            all_txns = search_history(history(), (lambda t: t.state is TxnState.ReqInCompleter))
            valid = set_comp_valid and all_txns

            if valid:
                idx,txn = all_txns[comp_index % len(all_txns)]
                vr.payload = comp_payload
                vr.txn_id = txn.dest_id
                self.print(f'\t\t\t\t\t\t\t\tCompleter completion: payload={vr.payload} txn_id={vr.txn_id}')

                # tell the requester-side checker what to expect
                history().replace(idx, TxnTracker(
                    source_id = txn.source_id,
                    dest_id = txn.dest_id,
                    req_payload = txn.req_payload,
                    comp_payload = vr.payload,
                    state = TxnState.CompInDut,
                ))
            vr.valid = valid

        # capture any requests that were sent to the completer
        vr = self.req_in
        if vr.valid and vr.ready:
            # check for unique-ID at completer side
            if not Config.suppress_implementation_checks:
                assert not search_history(history(), (
                    lambda t: t.state is TxnState.ReqInCompleter and t.dest_id == vr.txn_id
                ))

            # record the ID so that we can send a response
            history().append(TxnTracker(
                source_id = vr.txn_id & (2**Config.source_id_width - 1),
                dest_id = vr.txn_id,
                req_payload = vr.payload,
                state = TxnState.ReqInCompleter,
            ))
            self.print(f'\t\t\t\tCompleter request: payload={vr.payload} txn_id={vr.txn_id}')

        # set ready signals for next clock cycle
        self.req_in.ready = set_req_ready


class RobImplSimulator(ClockedSimulator):
    def __init__(self, *a, **ka):
        super().__init__(*a, **ka)
        # now split rules into subsets according to the valid/ready conditions
        # assumes only top-level (testbench) rules take input (parameters) from simulator
        # requires single-clock
        assert len(self.clocks) == 1
        clock,clock_name = self.clocks[0]
        assert clock_name == 'clk'

        self.non_tb_rules = [r for r in clock.rules if r.component is not self.system]
        assert all(not r.params for r in self.non_tb_rules)
        print('found non-TB rules:', len(self.non_tb_rules), 'out of', len(clock.rules))

        req_a = clock.rules_by_method[self.system.requester_a_clk]
        self.req_a_rules = {
            (rv, cr): [r for r in req_a if r.params['set_req_valid'] == rv and r.params['set_comp_ready'] == cr]
            for rv in (True,False) for cr in (True,False)
        }
        req_b = clock.rules_by_method[self.system.requester_b_clk]
        self.req_b_rules = {
            (rv, cr): [r for r in req_b if r.params['set_req_valid'] == rv and r.params['set_comp_ready'] == cr]
            for rv in (True,False) for cr in (True,False)
        }
        comp = clock.rules_by_method[self.system.completer_clk]
        self.comp_rules = {
            (cv, rr): [r for r in comp if r.params['set_comp_valid'] == cv and r.params['set_req_ready'] == rr]
            for cv in (True,False) for rr in (True,False)
        }
        print('found req-a tb rules:', [len(v) for k,v in self.req_a_rules.items()])
        print('found req-b tb rules:', [len(v) for k,v in self.req_b_rules.items()])
        print('found comp tb rules:', [len(v) for k,v in self.comp_rules.items()])

    def select_rules(self, clock, clock_name):
        # there is only one clock in this testbench
        assert clock_name == 'clk'

        req_a_valid = self.rand_gen.random() < Config.pr_new_req
        comp_a_ready = self.rand_gen.random() < Config.pr_accept_comp
        req_a = self.req_a_rules[(req_a_valid, comp_a_ready)]

        req_b_valid = self.rand_gen.random() < Config.pr_new_req
        comp_b_ready = self.rand_gen.random() < Config.pr_accept_comp
        req_b = self.req_b_rules[(req_b_valid, comp_b_ready)]

        req_ready = self.rand_gen.random() < Config.pr_accept_req
        comp_valid = self.rand_gen.random() < Config.pr_comp
        comp = self.comp_rules[(comp_valid, req_ready)]

        return self.non_tb_rules + [self.rand_gen.choice(r) for r in (req_a, req_b, comp)]

    if False:
        def run_one_step(self, final_time_ps, show_print, print_headers):
            for _ in super().run_one_step(final_time_ps, show_print, print_headers):
                if True:
                    print('##', 'Requester A side')
                    for h in self.system.requester_a_history:
                        print('##', '   ', h)
                    print('##', 'Requester B side')
                    for h in self.system.requester_b_history:
                        print('##', '   ', h)
                    print('##', 'Completer side')
                    for h in self.system.completer_history:
                        print('##', '   ', h)
                yield


# run simulation if imported as a top-level test
if __name__ == args.test_name + '_test':
    import random
    print('done import')
    tb = Implementation_Testbench()
    # elaboration takes a long time because the number of rules is huge
    print('done elaboration')
    seed = random.randrange(0x1_0000_0000)
#    seed = 3994852814
    sim = RobImplSimulator(tb, dict(frequency_GHz = 1.0, name = 'clk'), random_seed = seed)
    print('done building simulator, seed =', seed)
    n = 100 if args.quick else 100000
    sim.run(cycles_of_fastest_clock = n, print_headers = False)

    print('Free:', tb.dut.any_free_tq, tb.dut.two_free_tq, tb.dut.first_free_tq)
    print('Req:', tb.dut.any_req_tq, tb.dut.oldest_req_tq, tb.dut.newest_req_tq)
    for i,c in enumerate(tb.dut.txn_queue):
        print(i, c)
