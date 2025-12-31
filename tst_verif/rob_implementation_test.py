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

from purple import Integer, ModuloInteger, Boolean, Model, Record, Generic, Port, Clock, Registered_Output_Port
from rob_spec_test import Config, Types
from cli import args

class Config(Config):
    pr_new_req = 0.3
    pr_accept_req = 0.5
    pr_comp = 0.3
    pr_accept_comp = 0.5


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
    first_free_tq: ContextNumber = 0
    any_req_tq: Boolean = False
    oldest_req_tq: ContextNumber
    newest_req_tq: ContextNumber
    round_robin_start: ModuloInteger[2**Config.source_id_width] = 0

    request_in: ValidReadyIn[Types.Payload, Types.RequesterId]
    request_out: ValidReadyOut[Types.Payload, Types.CompleterId]
    completion_in: ValidReadyIn[Types.Payload, Types.CompleterId]
    completion_out: ValidReadyOut[Types.Payload, Types.RequesterId]

    clk: Clock[on_clk_edge]

    def on_clk_edge(self):
        # single rule, so that state updates become visible immediately in a defined order
        returned_tq = self.clk_send_comp_to_requester(self.completion_out)
        self.clk_capture_completion(self.completion_in)
        self.clk_send_req_to_completer(self.request_out)
        self.clk_capture_req(self.request_in)

        # send-comp-to-completer does not change free-queue state
        # capture-req pops from free-queue so here it is in a clean state and can be modified again
        if returned_tq is not None:
            tq = self.txn_queue[returned_tq]
            tq.next = self.first_free_tq
            tq.next_valid = self.any_free_tq
            self.any_free_tq = True
            self.first_free_tq = returned_tq

        self.completion_in.ready = True
        self.request_in.ready = self.any_free_tq

    def clk_capture_req(self, vr):
        if (not vr.ready) or (not vr.valid):
            return

        assert self.any_free_tq
        tq_id = self.first_free_tq
        tq = self.txn_queue[tq_id]

        if tq.next_valid:
            self.first_free_tq = tq.next
        else:
            self.any_free_tq = False

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
        if tq.source_id != vr.txn_id - (tq_id << Config.source_id_width):
            print('BANG', tq_id, tq)
            print('BANG', vr.txn_id)
        assert tq.source_id == vr.txn_id - (tq_id << Config.source_id_width)
        assert not tq.resp_valid

        tq.resp_valid = True
        tq.payload = vr.payload

    def clk_send_comp_to_requester(self, vr):
        if vr.valid and not vr.ready:
            return None

        candidates = [(i,t) for i,t in enumerate(self.txn_queue) if t.in_resp_queue and t.resp_valid and t.oldest]

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


if __name__ == args.test_name + '_test':
    # self-test for the clocked version
    from purple import ClockedSimulator, Tuple

    # should fix the lack of external inputs to clocked rules and then remove random
    import random

    class Txn(Record):
        source_id: Integer[...]
        dest_id: Integer[...]
        req_payload: Integer[...]
        resp_payload: Integer[...]
        dest_id_valid: Boolean
        resp_payload_valid: Boolean

    def rand_int(int_type):
        min_val,max_val = int_type.param_bounds
        return random.randrange(min_val, max_val)


    class Testbench(Model):
        history: Tuple[Txn]

        req_out: ValidReadyOut[Types.Payload, Types.RequesterId]
        req_in: ValidReadyIn[Types.Payload, Types.CompleterId]
        comp_out: ValidReadyOut[Types.Payload, Types.CompleterId]
        comp_in: ValidReadyIn[Types.Payload, Types.RequesterId]

        dut: ReOrderBuffer[
            bind_valid_ready(_.request_in, req_out),
            bind_valid_ready(req_in, _.request_out),
            bind_valid_ready(_.completion_in, comp_out),
            bind_valid_ready(comp_in, _.completion_out),
        ]

        clk: Clock[on_clock_edge, dut.clk]

        def on_clock_edge(self):
            # receive completions and check ordering
            vr = self.comp_in
            if vr.valid and vr.ready:
                # find the oldest transaction with matching requester-side ID
                all_txns = self.match_txns(lambda t: t.source_id == vr.txn_id)
                idx,txn = all_txns[0]

                assert txn.dest_id_valid
                assert txn.resp_payload_valid
                assert txn.resp_payload == vr.payload

                self.history.pop(idx)
                self.print(f'\t\t\t\t\t\t\t\t\t\t\t\tRequester completion: payload={vr.payload} txn_id={vr.txn_id}')

            # send completions, possibly out of order
            vr = self.comp_out
            if (vr.ready or not vr.valid):
                all_txns = self.match_txns(lambda t: t.dest_id_valid and not t.resp_payload_valid)
                valid = all_txns and random.random() < Config.pr_comp

                if valid:
                    idx,txn = random.choice(all_txns)
                    vr.payload = rand_int(Types.Payload)
                    vr.txn_id = txn.dest_id
                    self.print(f'\t\t\t\t\t\t\t\tCompleter completion: payload={vr.payload} txn_id={vr.txn_id}')

                    # tell the requester-side checker what to expect
                    self.history.replace(idx, Txn(
                        source_id = txn.source_id,
                        dest_id = txn.dest_id,
                        req_payload = txn.req_payload,
                        resp_payload = vr.payload,
                        dest_id_valid = True,
                        resp_payload_valid = True,
                    ))
                vr.valid = valid

            # capture any requests that were sent to the completer
            vr = self.req_in
            if vr.valid and vr.ready:
                # check for unique-ID at completer side
                assert not self.match_txns(
                    lambda t: t.dest_id_valid and t.dest_id == vr.txn_id and not t.resp_payload_valid)

                # find oldest transaction with matching requester-side ID
                source_id = vr.txn_id & (2**Config.source_id_width - 1)
                all_txns = self.match_txns(lambda t: t.source_id == source_id and not t.dest_id_valid)
                idx,txn = all_txns[0]

                # record the ID so that we can send a response
                self.history.replace(idx, Txn(
                    source_id = txn.source_id,
                    dest_id = vr.txn_id,
                    req_payload = txn.req_payload,
                    dest_id_valid = True,
                    resp_payload_valid = False,
                ))
                self.print(f'\t\t\t\tCompleter request: payload={vr.payload} txn_id={vr.txn_id}')

            # inject new requests
            vr = self.req_out
            if (vr.ready or not vr.valid):
                valid = random.random() < Config.pr_new_req
                if valid:
                    vr.payload = rand_int(Types.Payload)
                    vr.txn_id = rand_int(Types.RequesterId)
                    self.print(f'Requester request: payload={vr.payload} txn_id={vr.txn_id}')
                    self.history.append(Txn(
                        source_id = vr.txn_id,
                        req_payload = vr.payload,
                        dest_id_valid = False,
                        resp_payload_valid = False,
                    ))
                vr.valid = valid

            # set ready signals for next clock cycle
            self.req_in.ready = (random.random() < Config.pr_accept_req)
            self.comp_in.ready = (random.random() < Config.pr_accept_comp)

        def match_txns(self, filter):
            return [(i,t) for i,t in enumerate(self.history) if filter(t)]


    tb = Testbench()
    sim = ClockedSimulator(tb, dict(frequency_GHz = 1.0, name = 'clk'))
    n = 100 if args.quick else 10000
    try:
        sim.run(cycles_of_fastest_clock = n, print_headers = False)
    except AssertionError:
        raise

    print('Free:', tb.dut.any_free_tq, tb.dut.first_free_tq)
    print('Req:', tb.dut.any_req_tq, tb.dut.oldest_req_tq, tb.dut.newest_req_tq)
    for i,c in enumerate(tb.dut.txn_queue):
        print(i, c)
