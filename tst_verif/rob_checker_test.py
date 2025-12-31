'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Want to compare an atomic-rule and clocked implementation of the same thing

Well, want to verify the clocked using the atomic
This file is the testbench containing both the spec and implementation
And comparison between them

Initial approach is fully manual (here)
Will see which parts of it make sense to move to be aprt of Purple

Next
    Fix the recursion depth problem
        non-recursive search implementation done
        passing but very slow for 10000 cycles
            not too bad without printout, can even do 100000 cycles
        is time proportional or does it get slower as history gets longer?
            manual observation indicates no speed degradation during long simulation
            however this is for a passing simulation, not sure what will happen for a failure
            especially a failure after many cycles have been run
        which rules are getting run and reverted?
        slowness is presumably a consequence of running the wrong rule
            worse when it passes
            extreme case when a subsequent rule also passes
        what wrong rules can pass?
            NOT new input req (always right, but can fail)
            NOT on_request; it sends an output so if wrong it fails
            NOT send_completion; it sends an output
            NOT on_completion; asserts if context not primed (if latest completion too early)
            new input comp: can be too early in which case it passes
                in which case send_completion will fail
                but new-req, on-req should be available so there's no "revert" case
        so clearly I don't understand: in what circumstances is there a "revert"?
            on testing, it seems maybe there is never a revert
            so why does it take so long some times?
            do I have a potential infinite sequence of invocations without outputs to test?
            print when rule history gets longer
    Search for valid rule sequences testing
        1. negative testing; how long does it take to report impossible
            1.1 with frequent error, sometimes fast and sometimes a huge amount of time
                looks like (based on 100-cycle case) it will report eventually
                spec.send_completion allows any order among IDs, DUT has a round-robin arbiter
                investigate why (see above what-wrong-rules-can-pass)
                seems that it spends a long time reverting from 18 (OK) or 21 (effectively infinite)
                so only need a short history to require reverting and we're screwed
                have instrumented so we can see the history that needs reverting
                after the DUT produces a wrong completion we can continue to send requests
                    and completions into the spec, filling the reorder buffer with other completions
                    (if they come out they mismatch and we do something else)
                    so we can end up with a full reorder buffer (6 waiting completions) before we have a deadlock
                    now after reverting a few rules we may be able to send a new request and get back to
                    the same situation
            1.2 with error after some 1000s of OK cases
        2. speed testing: better random or whatever order is preferred
        3. depth testing: how many rules are being run (relative to rules accepted as part of history)
    Match spec state; so that you don't repeat an exhaustive search through rules
        will want a hash of the spec state to make comparisons fast (needs to save time not cost)
            possibly create hash incrementally when updating/reverting the state?
        eg use a python set() or dict() for already eliminated states
        state includes the read pointer on RTL IO queues but not the queue content
        may need to make the system into 2 separate things?
            no, because the sequential state does not change during checking
            yes want this anyway because the idea is to test against Verilog not always clocked-Purple
        if you use an incremental hash on system state
            ie built into Purple
            then it can be very fast to implement
            and you can store all system states that have been eliminated
            and only compare the hashes (super-fast)
            but this gives only "almost certain" outcome, so
                store a state that almost certainly is the same as one that got checked
                search for a state that passes
                if none found, go back to the almost-certainly-not case and check its entire
                    hierarchical state (in the unlikely event it is different, test it exhaustively)
                    can assume all different in first instance, to see if it solves speed issue
                    then later do the checking of same-hash
            hash can be eg hash(leaf.name)*(hash(leaf.name) + hash(leaf.value))
                this can be optimised to
                    leaf_name_hash_squared_clipped_to_64bit + leaf_name_hash * hash(leaf.value)
                or
                    leaf_name_hash_a + leaf_name_hash_b * hash(leaf.value)
                    xor this with the system state hash when setting/resetting the value
                    multiplying by the leaf-name means that same-value in different leaves
                        do not cancel each other out, eg (a=5, b=4) -> (a=4, b=5)
                    adding the leaf-name-hash-a should protect against 0; multiplying by
                        zero removes hash-b and in python hash(0) == 0
                so a top-level model instance contains a _dp_state_hash value which an invocation can
                    modify in-place (apply or revert changes, or modify-some-leaf-immediate)
                probably does not need to be initialised (initialised to a constant eg 0)

    Consider how you would replace the clocked sim with an RTL cosim
        see above separate the system
    Convert spec model to use pulls on input ports (saves a few rules)
    Add dual completers to system (makes for more interesting ordering of completions)
        Add a second implementation which stalls on repeated ID, no buffer
    Move the processing per interface into the generic class
        pass a converter method to make a packet?
        only interesting one is where I need to pull a txn_id from history, not invent one

Overall Plan
    Auto-create a testbench for the RTL-DUT using the spec-DUT as reference model
    For now, inputs are FIFO-input-port and outputs are (push) Port
    Make a testbench Model
        For each DUT input, create
            metching output (push) Port
            state FIFO (Tuple) of things to sent to it
        For each DUT output, create
            state FIFO of things witnessed at it
            matching input port with handler that checks new value against oldest
                in FIFO and pops or guards(?)
    Make a simulator
        Instantiates the clocked RTL DUT in its clocked testbench
            Testbench is needed for actual stimulus, does not need checking
            Maybe make a new testbench (see below)
        Instantiates the atomic-rule spec-model in its auto-testbench (above)
        Simulation
            run K clock cycles or K additions to stim output
                start with 1 output
            search for a rule sequence that matches
                note that any rule sequence not producing output will match
                    so require all output to be matched (is this always possible?)
                    but can you have an infinite sequence of rules that produces
                        no output, leading to infinite search?
                    not in this example:
                        on-req/on-comp are limited by the stim queues
                        send-completeion generates output
                    so output mismatch is a guard() and failure is a deadlock
                keep the whole history so that we can go all the way back
                option to keep only the last N rules of history
        How do we send observations to auto-testbench?
            manual code built into RTL testbench (create Record objects etc)
            so start by writing the whole thing manually as an atomic-rule-inside-
            clocked simulator
            ie a clocked process calls the atomic-rule?
        Actually looks like I can have 2 separate testbenches
'''

from purple import (
    Model, Record, Leaf,
    Integer, Tuple,
    Clock, Port, Generic,
    ClockedSimulator,
    GuardFailed, UnSelected, UnDefined,
)
from rob_spec_test import Config, Types, ReOrderBufferSpec
from rob_implementation_test import ReOrderBuffer, ValidReadyIn, ValidReadyOut, bind_valid_ready
from cli import args
import random

class Config(Config):
    pr_new_req = 0.3
    pr_accept_req = 0.5
    pr_comp = 0.3
    pr_accept_comp = 0.5


def rand_int(int_type):
    min_val,max_val = int_type.param_bounds
    return random.randrange(min_val, max_val)


@Generic
def HybridQueue(entry_cls):
    ''' a state element specific to the hybrid simulator

    used instead of Tuple for speed (Tuple has to build a new tuple every time we append to it)
    can be reverted, but expected mainly to be used in unguarded clocked rules

    only supports append()
    supports peek() and pop() from another state object
    this way, pop and push events can be reverted independently of each other
    so that a clocked rule can add stuff to the storage and an atomic rule can pop it out
    and if the atomic rule is reverted, recent additions to the queue are not discarded
    '''
    frozen_entry_cls = entry_cls._dp_make_frozen_class()

    class HybridQueue_base:
        _dp_class_cache_key = frozen_entry_cls
        param_entry_cls = frozen_entry_cls
        freeze_new_entries = (frozen_entry_cls is not entry_cls)
        entry_cls_is_leaf = issubclass(frozen_entry_cls, Leaf)

        @classmethod
        def check_and_freeze_value(cls, owner, name, value):
            v_frozen = value.freeze() if cls.freeze_new_entries else value
            if cls.entry_cls_is_leaf:
                return cls.param_entry_cls._dp_check_and_cast_including_undef(owner, name, v_frozen)
            else:
                assert isinstance(v_frozen, cls.param_entry_cls)
                return v_frozen

        @classmethod
        def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
            if value is UnSelected and allow_unsel:
                return value
            elif isinstance(value, HybridQueueObject.Push):
                # result of push() operation: append the new value and retain the same store (list object)
                # undoing a push will leave the value in the list but the length will go back to what it was
                new_entry = cls.check_and_freeze_value(owner, name, value.value)
                v_checked = value.hq_object.store
                length = value.hq_object.length
                if length == len(v_checked):
                    v_checked.append(new_entry)
                else:
                    assert length < len(v_checked)
                    v_checked[length] = new_entry
                length += 1
            else:
                if value is UnDefined:
                    v_checked = []
                    length = 0
                else:
                    v_checked = [cls.check_and_freeze_value(owner, name, v) for v in value]
                    length = len(v_checked)
            return HybridQueueObject(owner, name, v_checked, length)

    cls_name = f'HybridQueue_{entry_cls.__name__}'
    return Leaf.subclass(cls_name, HybridQueue_base)

class HybridQueueObject:
    def __init__(self, owner, name, iterable, length):
        assert isinstance(iterable, list)
        self.length = length
        self.store = iterable
        self.owner = owner
        self.name = name

    class Push:
        def __init__(self, hq_object, value):
            self.hq_object = hq_object
            self.value = value

    def push(self, value):
        setattr(self.owner, self.name, self.Push(self, value))

    def __len__(self):
        return self.length

    def __bool__(self):
        return self.length > 0

    def peek(self, index):
        GuardFailed.insist(index.index < self.length)
        return self.store[index.index]

    def pop(self, index):
        rv = self.peek(index)
        index.index += 1
        return rv

class HybridQueueIndex(Record):
    index: Integer[...] = 0


@Generic
def Input(payload_type, id_type, record_type):
    class SpecInput_cls(Model):
        dut_ports: ValidReadyOut[payload_type, id_type]
        spec_port: Port[record_type]

        queue: HybridQueue[record_type]
        queue_index: HybridQueueIndex

        rules: [send_rtl_input_to_spec]

        def send_rtl_input_to_spec(self):
            self.spec_port = self.queue.pop(self.queue_index)

    return SpecInput_cls


@Generic
def Output(payload_type, id_type, record_type):
    class SpecOutput_cls(Model):
        dut_ports: ValidReadyIn[payload_type, id_type]
        spec_port: Port[record_type] >> check_spec_output_matches_rtl

        queue: HybridQueue[record_type]
        queue_index: HybridQueueIndex

        def check_spec_output_matches_rtl(self, sample):
            self.guard(self.queue.pop(self.queue_index) == sample)

    return SpecOutput_cls


class Testbench(Model):
    'copy of implementation testbench with checking done by the spec model'
    completer_history: Tuple[Types.CompleterId]

    new_req: Input[Types.Payload, Types.RequesterId, Types.RequesterPacket]
    req_to_completer: Output[Types.Payload, Types.CompleterId, Types.CompleterPacket]
    comp_from_completer: Input[Types.Payload, Types.CompleterId, Types.CompleterPacket]
    comp_to_requester: Output[Types.Payload, Types.RequesterId, Types.RequesterPacket]

    dut: ReOrderBuffer[
        bind_valid_ready(_.request_in, new_req.dut_ports),
        bind_valid_ready(req_to_completer.dut_ports, _.request_out),
        bind_valid_ready(_.completion_in, comp_from_completer.dut_ports),
        bind_valid_ready(comp_to_requester.dut_ports, _.completion_out),
    ]

    spec: ReOrderBufferSpec[
        _.request_in                << new_req.spec_port,
        req_to_completer.spec_port  << _.request_out,
        _.completion_in             << comp_from_completer.spec_port,
        comp_to_requester.spec_port << _.completion_out,
    ]

    clk: Clock[on_clock_edge, dut.clk]

    def on_clock_edge(self):
        # receive completions at requester
        interface = self.comp_to_requester
        vr = interface.dut_ports
        if vr.valid and vr.ready:
            if False:
                packet = Types.RequesterPacket(payload = vr.payload, txn_id = vr.txn_id)
            else:
                # hack to create error pretty often
                # DUT producing a correct packet, which the spec can also produce
                # we modify it to something the spec cannot produce
                packet = Types.RequesterPacket(payload = vr.payload, txn_id = vr.txn_id | 6)
            interface.queue.push(packet)

            self.print(f'\t\t\t\t\t\t\t\t\t\t\t\tRequester completion: {packet}')

        # send completions from completer, possibly out of order
        interface = self.comp_from_completer
        vr = interface.dut_ports
        if (vr.ready or not vr.valid):
            valid = self.completer_history and random.random() < Config.pr_comp
            if valid:
                idx = random.randrange(len(self.completer_history))
                vr.payload = rand_int(Types.Payload)
                vr.txn_id = self.completer_history.pop(idx)

                packet = Types.CompleterPacket(payload = vr.payload, txn_id = vr.txn_id)
                interface.queue.push(packet)

                self.print(f'\t\t\t\t\t\t\t\tCompleter completion: {packet}')

            vr.valid = valid

        # capture any requests that were sent to the completer
        interface = self.req_to_completer
        vr = interface.dut_ports
        if vr.valid and vr.ready:
            self.completer_history.append(vr.txn_id)

            packet = Types.CompleterPacket(payload = vr.payload, txn_id = vr.txn_id)
            interface.queue.push(packet)

            self.print(f'\t\t\t\tCompleter request: {packet}')

        # inject new requests
        interface = self.new_req
        vr = interface.dut_ports
        if (vr.ready or not vr.valid):
            valid = random.random() < Config.pr_new_req
            if valid:
                vr.payload = rand_int(Types.Payload)
                vr.txn_id = rand_int(Types.RequesterId)

                packet = Types.RequesterPacket(payload = vr.payload, txn_id = vr.txn_id)
                interface.queue.push(packet)

                self.print(f'Requester request: {packet}')

            vr.valid = valid

        # set ready signals for next clock cycle
        self.req_to_completer.dut_ports.ready = (random.random() < Config.pr_accept_req)
        self.comp_to_requester.dut_ports.ready = (random.random() < Config.pr_accept_comp)


class CheckerSimulator(ClockedSimulator):
    def __init__(self, system, *clock_inputs):
        super().__init__(system, *clock_inputs)
        self.all_spec_rules = tuple(self.system.find_rule())
        self.spec_invocation_history = []

    def run(self,
        duration_ps = None,
        cycles = None,
        cycles_of_fastest_clock = None,
        show_print = True,
        print_headers = True,
    ):
        final_time_ps = self.sim_end_time(duration_ps, cycles, cycles_of_fastest_clock)

        for step in self.run_one_step(final_time_ps, show_print, print_headers):
            #### ADD STUFF HERE? MAYBE NOT NEEDED ####
            pass

        print('Searching for Spec Match')
        assert self.search_for_spec_rule_sequence(), 'no rule sequence found for spec that matches RTL'

    def search_for_spec_rule_sequence(self):
        ''' invoke/revert atomic rules

        idea is to keep going till the DUT output queues are empty - all matched against spec outputs
        need to fully empty the queues in most cases, otherwise an erroneous output might
        go unnoticed for a long time

        queue history is infinite
        could in many cases be restricted eg to 100 samples per port with minimal risk of
        needing to go back further to find a rule sequence that works
        this would save memory but maybe not any faster

        an arbitrary rule sequence can create illegal stimulus for the spec model
        eg if the request is not yet sent to the spec model, but the completion
            is already in the input queue
        may be able to use guards rather than assertions in the spec model
            this requires use of pull-semantic input ports rather than push-semantic with FIFO
            better anyway; fewer rules to search/revoke
        for now just ignore assertions in the spec model (treat like guards)

        recursive implementation cannot do more than a few hundred output packets
            because of Python limits (and if they are removed, very inefficient)
        '''
        rule_history = []
        index_history = [0]
        num_rules = len(self.all_spec_rules)

        while self.num_unmatched_outputs() > 0:
            # find an unguarded rule without any assertions in it
            while index_history[-1] < num_rules:
                rule = self.all_spec_rules[index_history[-1]]
                index_history[-1] += 1

                try:
                    result = rule.invoke(check = True, print_headers = False, show_print = False)
                except AssertionError:
                    continue

                if not result.guarded:
                    # add unguarded rule to the history and start testing from rule 0 with new history
                    rule_history.append(result)
                    index_history.append(0)
                    break

            else:
                # no unguarded rule can be found, remove the newest rule from the
                # history and continue searching from where we were
                if len(rule_history) == 0:
                    return False

                failed_rule = rule_history.pop(-1)
                failed_rule.revert_state()
                index_history.pop(-1)

        self.spec_invocation_history = rule_history
        return True

    def search_for_spec_rule_sequence_with_print(self):
        rule_history = []
        index_history = [0]
        num_rules = len(self.all_spec_rules)

        indent = ''
        while self.num_unmatched_outputs() > 0:
            while index_history[-1] < num_rules:
                rule = self.all_spec_rules[index_history[-1]]
                print(indent, index_history[-1], '/', num_rules, rule)
                index_history[-1] += 1

                try:
                    result = rule.invoke(check = True, print_headers = False, show_print = False)
                except AssertionError:
                    print(indent, 'Assert')
                    continue

                print(indent, result.guarded, self.num_unmatched_outputs(), len(rule_history))
                if not result.guarded:
                    if True:
                        nr = len(rule_history)
                        if nr % 1000 == 0:
                            print(nr)

                    rule_history.append(result)
                    index_history.append(0)
                    indent += '  '
                    break

            else:
                print('Revert')
                if len(rule_history) > 20:
                    for r in rule_history:
                        print(r.rule)
                    return False

                if len(rule_history) == 0:
                    return False

                failed_rule = rule_history.pop(-1)
                failed_rule.revert_state()
                index_history.pop(-1)
                indent = indent[:-2]

        self.spec_invocation_history = rule_history
        return True

    def num_unmatched_outputs(self):
        tb = self.system
        r2c = tb.req_to_completer
        c2r = tb.comp_to_requester
        return r2c.queue.length + c2r.queue.length - r2c.queue_index.index - c2r.queue_index.index


tb = Testbench()

sim = CheckerSimulator(tb, dict(frequency_GHz = 1.0, name = 'clk'))

print('Rules found:')
for r in sim.all_spec_rules:
    print(' ', r)

n = 100 if args.quick else 10000
sim.run(cycles_of_fastest_clock = n, print_headers = False)

if False:
    print('Queues at end of sim:')
    for intf in (tb.new_req, tb.req_to_completer, tb.comp_from_completer, tb.comp_to_requester):
        rd = intf.queue_index.index
        wr = intf.queue.length
        print('  ', intf.name[-1], wr, rd)
        for i,p in enumerate(intf.queue.store):
            pre = '  ->' if i == wr else '     '
            post = '->' if i == rd else ''
            print(pre, p, post)
        if wr == len(intf.queue.store):
            print('      <->' if rd == len(intf.queue.store) else '      ->')

print('Number of rules invoked:', len(sim.spec_invocation_history))
print('Total number of unmatched outputs:', sim.num_unmatched_outputs())
