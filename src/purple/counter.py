'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple state type: Counter
    can be modified by multiple rules sensitive to the same clock
    only one rule can set the value
    if a rule sets the value, only that rule can add/subtract
    if no rule sets the value, multiple rules can add/subtract
    if any rule goes outside the range, this is guarded or error

Principle is commutativity:
    if the outcome would be the same independent of rule execution order, allowed
'''

import operator

from . import common, leaf, parameterise, state


class AddToCounter:
    def __init__(self, incr):
        self.incr = incr


class CounterChange(common.LeafStateChange):
    def __init__(self, component, leaf_name, value_after, set_value, increment_value, counter_cls):
        super().__init__(component, leaf_name, value_after)
        self.set_value = set_value
        self.increment_value = increment_value
        self.counter_cls = counter_cls
        self.sanity_check(True)

    def sanity_check(self, new_change):
        if self.set_value is None:
            assert self.increment_value is not None
            assert self.value_after == self.value_before + self.increment_value
        elif self.increment_value is None:
            assert self.set_value is not None
            assert self.value_after == self.set_value
        else:
            assert not new_change
            assert self.value_after == self.set_value + self.increment_value

    def merge_in_rule(self, previous_update):
        # a rule has changed the same leaf twice, changes accumulate
        # self (new change) can be either a set or an increment
        # previous can be both (if so, assumption is set first, increment second)
        if previous_update is not None:
            # keep the original value (before rule invocation)
            self.value_before = previous_update.value_before

            if self.set_value is None:
                # an increment operation
                #   retains any previous set-operation
                #   merges with previous incr
                self.set_value = previous_update.set_value
                if previous_update.increment_value is not None:
                    self.increment_value += previous.increment_value
            else:
                # a set operation
                #   discards all previous operations
                pass

        self.sanity_check(False)

    def merge_concurrent_rules(self, parallel_update):
        # two concurrent (clocked) rules have changed the same leaf twice
        # changes are only allowed if the end result is the same for either order of execution
        # for a counter, this means both rules increment the value, neither sets it
        if self.set_value is None and parallel_update.set_value is None:
            assert self.value_before == parallel_update.value_before
            self.increment_value += parallel_update.increment_value
            self.value_after = CounterValue(self.value_before + self.increment_value)
            self.sanity_check(False)
        else:
            name = '.'.join(self.component.name) + '.' + self.leaf_name
            common.NonDeterministicLeafChange.insist(False,
                f'Counter {name} does not support set from one rule and increment/set from another')

    def post_merge_check(self):
        self.counter_cls._dp_check_and_cast_including_undef(None, '', self.value_after)


CounterOutOfRange = common.PurpleException.subclass('CounterOutOfRange')


@parameterise.Generic
def Counter(limit, out_of_range_is_error = False):
    assert isinstance(limit, int) and limit > 0
    cls_name = f'Counter_{limit}'

    class CounterLeafState:
        param_limit = limit
        _dp_counter_out_of_range = CounterOutOfRange if out_of_range_is_error else common.GuardFailed

        @classmethod
        def _dp_check_and_cast(cls, owner, name, value):
            int_value = int(value)
            cls._dp_counter_out_of_range.insist(0 <= int_value < cls.param_limit)
            return CounterValue(int_value)

        @classmethod
        def _dp_instance_setattr_leaf_changes(cls, owner, name, current, value):
            # this needs to return a 1-tuple with a LeafStateChange in it
            # it calls check-and-cast
            # value is something castable to int, or an AddToCounter object
            if isinstance(value, AddToCounter):
                new_value = cls._dp_check_and_cast_including_undef(owner, name, current + value.incr)
                return (CounterChange(owner, name, new_value, None, value.incr, cls),)
            else:
                new_value = cls._dp_check_and_cast_including_undef(owner, name, value)
                return (CounterChange(owner, name, new_value, new_value, None, cls),)

        @classmethod
        def _dp_all_possible_values(cls):
            return range(cls.param_limit)

    return leaf.Leaf.subclass(cls_name, CounterLeafState)


class CounterValue(state.EmulatedIntegerBase):
    def int_binary_op(self, other, op):
        return op(self.value, other)

    def int_unary_op(self, op):
        return op(self.value)

    def inplace_op(self, other, op):
        try:
            int_other = int(other)
        except Exception:
            return NotImplemented

        if op is operator.iadd:
            return AddToCounter(int_other)
        elif op is operator.isub:
            return AddToCounter(-int_other)
        else:
            return op(self.value, int_other)

    def __repr__(self):
        return f'<Counter:{self.value}>'
