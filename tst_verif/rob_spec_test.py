'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Want to compare an atomic-rule and clocked implementation of the same thing

Well, want to verify the clocked using the atomic
This file is the atomic-rule implementation

A simple Re-order Buffer Structure

* Requests come in
* Their ID is extended and they are sent to a completer
* The completer sends responses
* The ROB sends the responses to the requester in order depending on the original ID
* The selection of completer ID is non-architectural (many different implementations are acceptable)
'''

from purple import Integer, Boolean, Record, Model, Port
from cli import args

class Config:
    payload_width = 4
    source_id_width = 3
    num_contexts = 6


class Types:
    Payload = Integer[2**Config.payload_width]
    RequesterId = Integer[2**Config.source_id_width]
    CompleterId = Integer[Config.num_contexts * 2**Config.source_id_width]

    class RequesterPacket(Record):
        payload: Payload
        txn_id: RequesterId

    class CompleterPacket(Record):
        payload: Payload
        txn_id: CompleterId


ContextNumber = Integer[Config.num_contexts]

class TxnContext(Record):
    occupied: Boolean = False
    source_id: Types.RequesterId
    resp_seen: Boolean
    response_payload: Types.Payload

    # linked-list for ordering same-id transactions
    oldest: Boolean
    newest: Boolean
    next: ContextNumber


class ReOrderBufferSpec(Model):
    txn_queue: Config.num_contexts * TxnContext

    request_in: Port[Types.RequesterPacket]
    request_out: Port[Types.CompleterPacket]

    completion_in: Port[Types.CompleterPacket]
    completion_out: Port[Types.RequesterPacket]

    rules: [
        on_request,         # get request from input port, store in buffer and send to output port
        on_completion,      # get completion from input port, store in buffer
        send_completion,    # if oldest, pop completion from buffer and send to output port
    ]

    def on_request(self, context_id: ContextNumber):
        req = self.request_in

        context = self.txn_queue[context_id]
        self.guard(not context.occupied)

        try:
            previous = next(c for c in self.txn_queue if c.occupied and c.source_id == req.txn_id and c.newest)
            previous.newest = False
            previous.next = context_id
            oldest = False
        except StopIteration:
            oldest = True

        self.txn_queue[context_id] = TxnContext(
            occupied = True,
            source_id = req.txn_id,
            resp_seen = False,
            oldest = oldest,
            newest = True,
        )

        self.request_out = Types.CompleterPacket(
            payload = req.payload,
            txn_id = (context_id << Config.source_id_width) | req.txn_id,
        )

    def on_completion(self):
        comp = self.completion_in

        context_id = comp.txn_id >> Config.source_id_width
        source_id = comp.txn_id - (context_id << Config.source_id_width)
        context = self.txn_queue[context_id]

        self.guard(context.occupied and context.source_id == source_id and not context.resp_seen)

        context.response_payload = comp.payload
        context.resp_seen = True

    def send_completion(self, context_id: ContextNumber):
        context = self.txn_queue[context_id]
        self.guard(context.occupied and context.resp_seen and context.oldest)

        self.completion_out = Types.RequesterPacket(
            payload = context.response_payload,
            txn_id = context.source_id,
        )

        if not context.newest:
            next_context = self.txn_queue[context.next]
            next_context.oldest = True

        context.occupied = False


if __name__ == args.test_name + '_test':
    # self-test for the atomic-rule version
    from purple import AtomicRuleSimulator, Tuple

    class TxnTracker(Record):
        source_id: Integer[...]
        dest_id: Integer[...]
        req_payload: Integer[...]
        resp_payload: Integer[...]
        dest_id_valid: Boolean
        resp_payload_valid: Boolean


    class Testbench(Model):
        history: Tuple[TxnTracker]

        request_out: Port[Types.RequesterPacket] << req_at_requester
        request_in: Port[Types.CompleterPacket] >> req_at_completer

        completion_out: Port[Types.CompleterPacket] << comp_at_completer
        completion_in: Port[Types.RequesterPacket] >> comp_at_requester

        next_req: Types.RequesterPacket
        next_req_valid: Boolean = False
        next_comp: Types.CompleterPacket
        next_comp_valid: Boolean = False

        rules: [gen_req, gen_comp]

        dut: ReOrderBufferSpec[
            _.request_in << request_out,
            _.request_out >> request_in,
            _.completion_in << completion_out,
            _.completion_out >> completion_in,
        ]

        def gen_req(self, packet: Types.RequesterPacket):
            # rule: creates a new request packet to start a transaction
            self.guard(not self.next_req_valid)
            self.next_req_valid = True
            self.next_req = packet
            self.history.append(TxnTracker(
                source_id = packet.txn_id,
                req_payload = packet.payload,
                dest_id_valid = False,
                resp_payload_valid = False,
            ))

        def req_at_requester(self):
            # port handler: sends the latest request packet to the DUT
            self.guard(self.next_req_valid)
            self.print('Requester request:', self.next_req)
            self.next_req_valid = False
            return self.next_req

        def req_at_completer(self, packet):
            # port handler: request received from DUT, testbench will later send a completion
            self.print('                                Completer request:', packet)

            # check for unique-ID at completer side
            assert not self.match_txns(lambda t: t.dest_id_valid and t.dest_id == packet.txn_id)

            # find oldest transaction with matching requester-side ID
            source_id = packet.txn_id & (2**Config.source_id_width - 1)
            all_txns = self.match_txns(lambda t: t.source_id == source_id and not t.dest_id_valid)
            idx,txn = all_txns[0]

            # record the ID so that we can send a response
            self.history.replace(idx, TxnTracker(
                source_id = txn.source_id,
                dest_id = packet.txn_id,
                req_payload = txn.req_payload,
                dest_id_valid = True,
                resp_payload_valid = False,
            ))

        def gen_comp(self, packet: Types.CompleterPacket):
            # rule: create a legal completion, for one of the requests that the DUT has sent
            self.guard(not self.next_comp_valid)

            # check there is exactly one transaction with matching ID on completer-side
            all_txns = self.match_txns(
                lambda t: t.dest_id_valid and packet.txn_id == t.dest_id and not t.resp_payload_valid
            )
            self.guard(all_txns)
            assert len(all_txns) == 1

            # tell the requester-side checker what to expect
            idx,txn = all_txns[0]
            self.history.replace(idx, TxnTracker(
                source_id = txn.source_id,
                dest_id = txn.dest_id,
                req_payload = txn.req_payload,
                resp_payload = packet.payload,
                dest_id_valid = True,
                resp_payload_valid = True,
            ))

            self.next_comp_valid = True
            self.next_comp = packet

        def comp_at_completer(self):
            # port handler: deliver the next completion to the DUT
            self.guard(self.next_comp_valid)
            self.print('Completer completion:', self.next_comp)
            self.next_comp_valid = False
            return self.next_comp

        def comp_at_requester(self, packet):
            # port handler: DUT has provided a completion, transaction is complete
            self.print('                                Requester completion:', packet)

            # find the oldest transaction with matching requester-side ID
            all_txns = self.match_txns(lambda t: t.source_id == packet.txn_id)
            idx,txn = all_txns[0]
            self.history.pop(idx)

            # check stuff
            assert txn.dest_id_valid
            assert txn.resp_payload_valid
            assert txn.resp_payload == packet.payload

        def match_txns(self, filter):
            return [(i,t) for i,t in enumerate(self.history) if filter(t)]


    tb = Testbench()
    sim = AtomicRuleSimulator(system = tb)
    n = 100 if args.quick else 10000
    try:
        sim.run(num_invocations = n, print_headers = False)
        assert not sim.deadlocked
    except AssertionError:
        print('--- TB')
        for t in tb.history:
            print(t)
        print('--- DUT')
        for t in tb.dut.txn_queue:
            print(t)
        raise
