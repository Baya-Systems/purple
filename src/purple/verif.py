'''
MIT Licence: Copyright (c) 2026 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Use an atomic-rule specification model to verify an (RTL) implementation

The implementation testbench is run, capturing the inputs and outputs of the implementation-DUT
A simple testbench for the spec is implemented which
    uses the implementation-DUT inputs as inputs to the spec-DUT
    checks whether any sequence of spec-DUT rules can create the implementation-GUT outputs

This file contains base classes to support creation of such a spec testbench,
and a search algorithm for finding whether a rule sequence exists matching the implementation
stimulus

Notes:
    only works if the entire history of the implementation-sim is available;
    cannot eg find a solution for the first 100 cycles then look for a solution for
    the next 100 keeping the same search history.  this is because some rule order
    options may have been ruled out during the search, which additional stimulus
    make possible/necessary
    this means the implementation-sim is either run in its entirety, or the rule
    check-search is paused and resumed as the implementation-sim advances
'''

from . import common, port, parameterise, model, leaf
import enum


StimulusQueueNeedsMoreData = common.PurpleException.subclass('StimulusQueueNeedsMoreData')

@parameterise.Generic
def StimulusQueue(entry_cls):
    ''' a state element specific to the hybrid simulator

    used instead of Tuple for speed (Tuple has to build a new tuple every time we append to it)

    pop() cannot be reverted, can be called from outside a rule
    peek() shows oldest
    pop() returns oldest and hides it; can be reverted by un-hiding
    __len__() exists but does not revert because affected by push() as well as pop()

    quasi-immutable model attributes of type StimulusQueueObject[entry-cls]:
        conceptually the objects store is complete the whole time
        on pop(), the Model attribute gets replaced with a new object (so we can revert)
        will raise a StimulusQueueNeedsMoreData exception if it can't behave as if its store is complete
        after this exception, it should normally be possible to add push more stimulus to the queue
        (eg by running some more of a clocked simulation) and then continue
    '''
    frozen_entry_cls = entry_cls._dp_make_frozen_class()

    class StimulusQueueObject:
        ''' the Model attribute for a StimulusQueue[] Leaf state element is an object of this class
        '''
        param_entry_cls = frozen_entry_cls
        freeze_new_entries = (frozen_entry_cls is not entry_cls)
        entry_cls_is_leaf = issubclass(frozen_entry_cls, leaf.Leaf)

        class SharedState:
            'object attributes that are not copy-by-value on pop(), do not change on revert()'
            def __init__(self, owner, name):
                self.owner = owner
                self.name = name
                self.store_is_complete = False
                self.max_read_pointer = 0
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

        def push(self, value, time_ps, store_is_complete = False):
            ss = self.shared_state
            assert not ss.store_is_complete
            if self.entry_cls_is_leaf:
                leaf = self.param_entry_cls
                v_frozen = leaf._dp_check_and_cast_including_undef(ss.owner, ss.name, value)
            else:
                v_frozen = value.freeze() if self.freeze_new_entries else value

            # require in-order stimulus capture
            assert (not ss.store) or time_ps >= ss.store[-1][1]
            ss.store.append((v_frozen, time_ps))
            ss.store_is_complete = store_is_complete

        def completed(self):
            self.shared_state.store_is_complete = True

        def all_matched(self):
            return len(self) == 0 and self.shared_state.store_is_complete

        def peek(self):
            ss = self.shared_state
            have_data = self.read_pointer < len(ss.store)
            if ss.store_is_complete:
                common.GuardFailed.insist(have_data)
            else:
                StimulusQueueNeedsMoreData.insist(have_data)
            return ss.store[self.read_pointer]

        def pop(self):
            rv = self.peek()
            ss = self.shared_state
            ss.max_read_pointer = max(self.read_pointer, ss.max_read_pointer)
            new_object = StimulusQueueObject(self.read_pointer + 1, ss)
            setattr(ss.owner, ss.name, new_object)
            return rv

    class StimulusQueue_base:
        _dp_class_cache_key = frozen_entry_cls
        param_entry_cls = frozen_entry_cls
        freeze_new_entries = (frozen_entry_cls is not entry_cls)
        entry_cls_is_leaf = issubclass(frozen_entry_cls, leaf.Leaf)
        attr_class = StimulusQueueObject

        @classmethod
        def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
            if isinstance(value, cls.attr_class):
                # result of push() operation
                return value
            elif value is common.UnDefined:
                # only the initial value during elaboration
                return cls.attr_class(0, cls.attr_class.SharedState(owner, name))
            else:
                assert False

    cls_name = f'StimulusQueue_{entry_cls.__name__}'
    return leaf.Leaf.subclass(cls_name, StimulusQueue_base)


@parameterise.Generic
def StimulusInput(entry_type):
    # binds to a pull-port in an atomic-rule Model
    # sends things in-order to that port from a stimulus queue
    class InputClass(model.Model):
        param_entry_type = entry_type
        queue: StimulusQueue[entry_type]
        port_for_spec_input: port.Port[entry_type] << get_next
        def get_next(self):
            data,time_ps = self.queue.pop()
            # don't continue with this input if we're only checking outputs that happened before it
            self.guard(self._dp_top_component.before_next_output(time_ps))
#            self.guard(self._dp_top_component.before_all_outputs(time_ps))
            return data
    return InputClass

@parameterise.Generic
def StimulusOutput(entry_type):
    # binds to a push-port in an atomic-rule Model
    # checks things from that port against an in-order stimulus queue
    # guards() not errors on mismatch, allowing a search for other rule order
    class OutputClass(model.Model):
        param_entry_type = entry_type
        queue: StimulusQueue[entry_type]
        port_for_spec_output: port.Port[entry_type] >> check_next
        def check_next(self, entry):
            data,_ = self.queue.pop()
            self.guard(data == entry)
    return OutputClass


class StimulusIOCheckerState:
    ''' sits outside the testbench, contains a search state
    '''
    StateEnum = enum.Enum('CheckerState', 'New WaitingForInput Passed Failed')

    def waiting_for_input(self):
        return self.state is self.StateEnum.WaitingForInput

    def passed(self):
        return self.state is self.StateEnum.Passed

    def failed(self):
        return self.state is self.StateEnum.Failed

    def wait_for_input(self):
        self.state = self.StateEnum.WaitingForInput
        return self

    def succeed(self):
        self.state = self.StateEnum.Passed
        return self

    def fail(self):
        self.state = self.StateEnum.Failed
        return self

    def __init__(self, spec_testbench):
        self.spec_testbench = spec_testbench
        self.rule_history = []
        self.index_history = [0]
        self.num_invocations = 0
        self.failing_state_hashes = set()
        self.num_hash_matches = 0
        self.all_rules = tuple(spec_testbench.find_rule())
        self.state = self.StateEnum.New

    def show(self, title, time_ps, total_ps):
        print('**', title, '**')
        print('  time simulated (ns):', time_ps / 1000, 'out of', total_ps / 1000)
        print('  current number of unmatched outputs:', self.spec_testbench.num_unmatched_outputs())
        print('  number of atomic rules in current history:', len(self.rule_history))
        print('  number of atomic rules tested:', self.num_invocations)
        print('  number of failing states found:', len(self.failing_state_hashes))
        print('  number of hash matches:', self.num_hash_matches)


class StimulusIOTestbenchBase(model.Model):
    def before_next_output(self, time_ps):
        sq = (i.queue for i in self.stimulus_outputs())
        return all((q.shared_state.store_is_complete or time_ps <= q.peek()[1]) for q in sq)

    def before_all_outputs(self, time_ps):
        sq = (i.queue for i in self.stimulus_outputs())
        return not any(((not q.shared_state.store_is_complete) and time_ps > q.peek()[1]) for q in sq)

    def stimulus_inputs(self):
        # return a tuple of (ref_to_something_in_implementation_testbench, StimulusInput)
        # unless implementation is None in which case (None, StimulusInput)
        raise TypeError('override stimulus_inputs() in model-specific testbench class')

    def stimulus_outputs(self):
        # return a tuple of (ref_to_something_in_implementation_testbench, StimulusOutput)
        # unless implementation is None in which case (None, StimulusInput)
        raise TypeError('override stimulus_outputs() in model-specific testbench class')

    def num_unmatched_outputs(self):
        return sum(len(sq.queue) for sq in self.stimulus_outputs())

    def any_unmatched_outputs(self):
        return not all(sq.queue.all_matched() for sq in self.stimulus_outputs())

    def finalise_all_stimulus(self):
        for sq in self.stimulus_inputs() + self.stimulus_outputs():
            sq.queue.completed()

    def report_after_fail(self, num_packets_to_report):
        earliest_nomatch = None

        print('Output Stimulus:')
        for sq in self.stimulus_outputs():
            print('   ', '.'.join(sq.name))
            ss = sq.queue.shared_state
            if ss.store:
                last_match, last_match_t = ss.store[ss.max_read_pointer]
                print('        last match', last_match_t, 'ps:', last_match)
                if len(ss.store) > 1 + ss.max_read_pointer:
                    first_nomatch, first_nomatch_t = ss.store[1 + ss.max_read_pointer]
                    print('        first unmatchable     ', first_nomatch_t, 'ps:', first_nomatch)
                    if earliest_nomatch is None or earliest_nomatch > first_nomatch_t:
                        earliest_nomatch = first_nomatch_t
            else:
                print('        no stimulus')

        if earliest_nomatch is None:
            earliest_nomatch = 0

        print('Input Stimulus before', earliest_nomatch, 'ps')
        for sq in self.stimulus_inputs():
            print('   ', '.'.join(sq.name))
            ss = sq.queue.shared_state
            if ss.store:
                vt = [
                    (v, t, 'UNUSED' if i > ss.max_read_pointer else '')
                    for i,(v,t) in enumerate(ss.store)
                    if t <= earliest_nomatch
                ]
                for v,t,note in vt[-num_packets_to_report:]:
                    print('        ', t, 'ps:', v, note)
            else:
                print('        no stimulus')

    def checksearch(self, checker_state, allow_zero_rules = False):
        '''
        search for a sequence of rules by which the spec model can
        match the inputs and outputs of the implementation model

        keep going till the DUT output queues are empty - all matched against spec outputs
        stop and request more stimulus as required

        queue history is infinite; stimulus is never deleted
        could in many cases be restricted eg to 100 samples per port with minimal risk of
        needing to go back further to find a rule sequence that works
        this would save memory but maybe not any faster

        does not test any further if it finds a state whose hash matches a previously
            exhaustively tested state
            this is a bit risky, because hashes can in theory match for different states
        '''
        if checker_state is None:
            checker_state = StimulusIOCheckerState(self)

        rule_history = checker_state.rule_history
        index_history = checker_state.index_history
        failing_state_hashes = checker_state.failing_state_hashes
        all_rules = checker_state.all_rules
        num_rules = len(all_rules)

        while self.any_unmatched_outputs():
            # find an unguarded rule without any assertions in it
            while index_history[-1] < num_rules:
                rule = all_rules[index_history[-1]]

                # check is false so that needs-more-data is trapped
                result = rule.invoke(check = False, print_headers = True, show_print = True)
                if result.exc_type is StimulusQueueNeedsMoreData:
                    return checker_state.wait_for_input()

                checker_state.num_invocations += 1
                index_history[-1] += 1

                if result.guarded:
                    # rule is not runnable (does not change spec state) so not useful
                    # state already reverted by rule.invoke()
                    pass

                elif result.exc_type:
                    raise result.exc_value

                elif self._dp_model_state_hash in failing_state_hashes:
                    # we have been to this spec state before and we know it doesn't go anywhere useful
                    checker_state.num_hash_matches += 1
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
                    return checker_state.fail()

                failed_rule = rule_history.pop(-1)
                index_history.pop(-1)
                failing_state_hashes.add(self._dp_model_state_hash)
                failed_rule.revert_state()

        if rule_history or allow_zero_rules:
            return checker_state.succeed()
        else:
            return checker_state.fail()
