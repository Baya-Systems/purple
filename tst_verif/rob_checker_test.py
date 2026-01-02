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
    unuseably slow to fail with systematic rule order search, just about OK with hash matching
    fast to pass, slow to fail
    failure does not give very helpful error reports, eg it fails a few thousand cycles after
        the event and has ultimately matched no stimulus at all
        maybe it should run again and try to get as far as it can?
    add a second implementation which stalls on repeated ID, no buffer
'''

from purple import Model, Leaf, Port, Generic, UnDefined, PurpleException, GuardFailed
from rob_spec_test import ReOrderBufferSpec
from rob_implementation_test import Config, Types, Implementation_Testbench, RobImplSimulator
from cli import args

class Config(Config):
    suppress_implementation_checks = True
    cycles_per_checksearch = 100 if args.quick else 1000
    total_cycles = 100 if args.quick else 10000
    cycles_to_bug_injection = 5500


StimulusQueueNeedsMoreData = PurpleException.subclass('StimulusQueueNeedsMoreData')

@Generic
def StimulusQueue(entry_cls):
    ''' a state element specific to the hybrid simulator

    used instead of Tuple for speed (Tuple has to build a new tuple every time we append to it)

    pop() cannot be reverted, can be called from outside a rule
    peek() shows oldest
    pop() returns oldest and hides it; can be reverted by un-hiding
    __len__() exists but does not revert because affected by push() as well as pop()
    '''
    frozen_entry_cls = entry_cls._dp_make_frozen_class()

    class StimulusQueueObject:
        ''' the Model attribute for a StimulusQueue[] Leaf state element is an object of this class

        quasi-immutable:
            conceptually it has its store complete the whole time
            on pop(), the Model attribute gets replaced with a new object (so we can revert)
            will raise a StimulusQueueNeedsMoreData exception if it can't behave as if its store is complete
            after this exception, it should normally be possible to add push more stimulus to the queue
            (eg by running some more of a clocked simulation) and then continue
        '''
        param_entry_cls = frozen_entry_cls
        freeze_new_entries = (frozen_entry_cls is not entry_cls)
        entry_cls_is_leaf = issubclass(frozen_entry_cls, Leaf)

        class SharedState:
            'object attributes that are not copy-by-value on pop(), do not change on revert()'
            def __init__(self, owner, name):
                self.owner = owner
                self.name = name
                self.store_is_complete = False
                self.store = list()

        def __init__(self, read_pointer, shared_state):
            self.read_pointer = read_pointer
            self.shared_state = shared_state

        def __eq__(self, other):
            return self.read_pointer == other.read_pointer

        @staticmethod
        def _dp_hash_function(the_queue):
            return hash(the_queue.read_pointer)

        def __str__(self):
            ss = self.shared_state
            name = '.'.join((*ss.owner.name, ss.name))
            return f'{name}/queue({self.read_pointer}, {len(ss.store)})'

        def __len__(self):
            return len(self.shared_state.store) - self.read_pointer

        def push(self, value, store_is_complete = False):
            ss = self.shared_state
            assert not ss.store_is_complete
            if self.entry_cls_is_leaf:
                leaf = self.param_entry_cls
                v_frozen = leaf._dp_check_and_cast_including_undef(ss.owner, ss.name, value)
            else:
                v_frozen = value.freeze() if self.freeze_new_entries else value
            ss.store.append(v_frozen)
            ss.store_is_complete = store_is_complete

        def completed(self):
            self.shared_state.store_is_complete = True

        def peek(self):
            ss = self.shared_state
            have_data = self.read_pointer < len(ss.store)
            (GuardFailed if ss.store_is_complete else StimulusQueueNeedsMoreData).insist(have_data)
            return ss.store[self.read_pointer]

        def pop(self):
            rv = self.peek()
            ss = self.shared_state
            new_object = StimulusQueueObject(self.read_pointer + 1, ss)
            setattr(ss.owner, ss.name, new_object)
            return rv

    class StimulusQueue_base:
        _dp_class_cache_key = frozen_entry_cls
        param_entry_cls = frozen_entry_cls
        freeze_new_entries = (frozen_entry_cls is not entry_cls)
        entry_cls_is_leaf = issubclass(frozen_entry_cls, Leaf)
        attr_class = StimulusQueueObject

        @classmethod
        def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
            if isinstance(value, cls.attr_class):
                # result of push() operation
                return value
            elif value is UnDefined:
                # only the initial value during elaboration
                return cls.attr_class(0, cls.attr_class.SharedState(owner, name))
            else:
                assert False

    cls_name = f'StimulusQueue_{entry_cls.__name__}'
    return Leaf.subclass(cls_name, StimulusQueue_base)


@Generic
def StimulusInput(entry_type):
    # binds to a pull-port in an atomic-rule Model
    # sends things in-order to that port from a stimulus queue
    class InputClass(Model):
        param_entry_type = entry_type
        queue: StimulusQueue[entry_type]
        port_for_spec_input: Port[entry_type] << get_next
        def get_next(self):
            return self.queue.pop()
    return InputClass

@Generic
def StimulusOutput(entry_type):
    # binds to a push-port in an atomic-rule Model
    # checks things from that port against an in-order stimulus queue
    # guards() not errors on mismatch, allowing a search for other rule order
    class OutputClass(Model):
        param_entry_type = entry_type
        queue: StimulusQueue[entry_type]
        port_for_spec_output: Port[entry_type] >> check_next
        def check_next(self, entry):
            self.guard(self.queue.pop() == entry)
    return OutputClass


class Spec_Testbench(Model):
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


class CheckerSimulator(RobImplSimulator):
    # extend clocked simulator to copy inputs and outputs after every cycle
    # and enable it to run the spec (atomic-rule) simulator as a tester
    def __init__(self, impl_random_seed = None):
        print('elaborating spec testbench')
        self.spec_testbench = Spec_Testbench()
        print('elaborating implementation testbench')
        clks = dict(frequency_GHz = 1.0, name = 'clk')
        impl_testbench = Implementation_Testbench()
        self.cycles = 0
        print('making implementation simulator')
        super().__init__(impl_testbench, clks, random_seed = impl_random_seed)

    def run_one_step(self, final_time_ps, show_print, print_headers):
        for _ in super().run_one_step(final_time_ps, show_print, print_headers):
            self.copy_implementation_io_to_spec_testbench()
            yield

    def stimulus_mapping(self):
        spec = self.spec_testbench
        impl = self.system
        return dict(
            inputs = (
                (impl.req_out_a, spec.new_req_a),
                (impl.req_out_b, spec.new_req_b),
                (impl.comp_out, spec.comp_from_completer),
            ),
            outputs = (
                (impl.req_in, spec.req_to_completer),
                (impl.comp_in_a, spec.comp_to_requester_a),
                (impl.comp_in_b, spec.comp_to_requester_b),
            ),
        )

    def copy_implementation_io_to_spec_testbench(self):
        # runs after every clock cycle
        sm = self.stimulus_mapping()
        for vr,sq in sm['inputs'] + sm['outputs']:
            PT = sq.param_entry_type
            if vr.valid and vr.ready:
                packet = PT(payload = vr.payload, txn_id = vr.txn_id)
                sq.queue.push(packet)

    def num_unmatched_outputs(self):
        return sum(len(sq.queue) for _,sq in self.stimulus_mapping()['outputs'])

    def finalise_stimulus(self):
        sm = self.stimulus_mapping()
        for _,sq in sm['inputs'] + sm['outputs']:
            sq.queue.completed()

    def checksearch(self, total_cycles, delta_cycles):
        '''
        search for a sequence of rules by which the spec model can
        match the inputs and outputs of the implementation model

        keep going till the DUT output queues are empty - all matched against spec outputs

        run the clocked (implementation) simulator as required to load more stimulus

        queue history is infinite; stimulus is never deleted
        could in many cases be restricted eg to 100 samples per port with minimal risk of
        needing to go back further to find a rule sequence that works
        this would save memory but maybe not any faster

        recursive implementation cannot do more than a few hundred output packets
            because of Python limits (and if they are removed, very inefficient)

        does not test any further if it finds a state whose hash matches a previously
            exhaustively tested state
            this is a bit risky, because hashes can in theory match for different states
        '''
        spec_testbench = self.spec_testbench
        rule_history = []
        index_history = [0]
        failing_state_hashes = set()
        all_rules = tuple(self.spec_testbench.find_rule())
        num_rules = len(all_rules)
        num_invocations = 0
        num_hash_matches = 0

        def run_implementation_from_checksearch(cycles_to_run):
            if isinstance(cycles_to_run, int):
                print('** Running implementation testbench to get more stimulus **')
                self.run(cycles = cycles_to_run, show_print = False, print_headers = False)
                new_cycles = self.cycles + cycles_to_run
                if new_cycles >= total_cycles:
                    # this will mean no further StimulusQueueNeedsMoreData exceptions
                    self.finalise_stimulus()
            else:
                print('**', cycles_to_run, '**')
                new_cycles = self.cycles

            print('  cycles simulated:', new_cycles, 'out of', total_cycles)
            print('  current number of unmatched outputs:', self.num_unmatched_outputs())
            print('  number of atomic rules in current history:', len(rule_history))
            print('  number of atomic rules tested:', num_invocations)
            print('  number of failing states found:', len(failing_state_hashes))
            print('  number of hash matches:', num_hash_matches)
            return new_cycles

        self.cycles = run_implementation_from_checksearch(delta_cycles)
        while self.cycles < total_cycles or self.num_unmatched_outputs() > 0:
            # find an unguarded rule without any assertions in it
            while index_history[-1] < num_rules:
                rule = all_rules[index_history[-1]]
                index_history[-1] += 1

                while True:
                    # check is false so that needs-more-data is trapped
                    result = rule.invoke(check = False, print_headers = False, show_print = False)
                    if result.exc_type is StimulusQueueNeedsMoreData:
                        self.cycles = run_implementation_from_checksearch(delta_cycles)
                    else:
                        break
                num_invocations += 1

                if result.guarded:
                    # rule is not runnable (does not change spec state) so not useful
                    # state already reverted by rule.invoke()
                    pass
                elif result.exc_type:
                    raise

                elif spec_testbench._dp_model_state_hash in failing_state_hashes:
                    # we have been to this spec state before and we know it doesn't go anywhere useful
                    num_hash_matches += 1
                    result.revert_state()

                else:
                    # successful rule invocation resulting in a new model state
                    # keep the state, add the rule to the history and start testing from rule 0 again
                    rule_history.append(result)
                    index_history.append(0)
                    break

            if index_history[-1] >= num_rules:
                # no plausible rule can be found, remove the newest rule from the
                # history and continue searching from where we were
                if len(rule_history) == 0:
                    run_implementation_from_checksearch('Failed to find a rule sequence')
                    return False

                failed_rule = rule_history.pop(-1)
                index_history.pop(-1)
                failing_state_hashes.add(spec_testbench._dp_model_state_hash)
                failed_rule.revert_state()

        run_implementation_from_checksearch('Found a rule sequence')
        return True


sim = CheckerSimulator()
assert sim.checksearch(Config.total_cycles, Config.cycles_per_checksearch)


if not args.quick:
    class BugInjectingSimulator(CheckerSimulator):
        def __init__(self, *a, **ka):
            super().__init__(*a, **ka)
            self.bug_injected = False

        def copy_implementation_io_to_spec_testbench(self):
            # runs after every clock cycle
            # but self.cycles only updated after a bunch of cycles
            # we will change an ID value, so the spec appears to see a bug in the implementation
            # this doesn't affect the implementation testbench which runs as normal
            sm = self.stimulus_mapping()
            for vr,sq in sm['inputs'] + sm['outputs']:
                PT = sq.param_entry_type
                if vr.valid and vr.ready:
                    if (not self.bug_injected) and self.cycles > Config.cycles_to_bug_injection:
                        packet = PT(payload = vr.payload, txn_id = vr.txn_id ^ 1)
                        self.bug_injected = True
                    else:
                        packet = PT(payload = vr.payload, txn_id = vr.txn_id)
                    sq.queue.push(packet)

    print('Now run with bug injection')
    sim2 = BugInjectingSimulator()
    assert not sim2.checksearch(Config.total_cycles, Config.cycles_per_checksearch)
