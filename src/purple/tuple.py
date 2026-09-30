'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple Tuple type


A Tuple is a Leaf state element containing an ordered list of any number of entries

The entries are transient frozen record objects, all the same type
This is a somewhat informal thing, as the conceptual storage required for it is unbounded
May be slow in simulation if the number of elements is large
Never UnDefined but defaults to empty

Can be put in a (transient) Record
'''

import enum

from . import common, parameterise, leaf


class TupleObject(tuple):
    def __new__(cls, owner, name, iterable):
        self = super().__new__(cls, iterable)
        self.owner = owner
        self.name = name
        return self

    def pop(self, index = 0):
        previous = self[index]
        setattr(self.owner, self.name, PopTuple(index, None))
        return previous

    def replace(self, index, value):
        previous = self[index]
        setattr(self.owner, self.name, ReplaceTuple(index, value))
        return previous

    def insert(self, index, value):
        setattr(self.owner, self.name, InsertTuple(index, value))

    def append(self, value):
        setattr(self.owner, self.name, AppendTuple(None, value))


class TupleOperation:
    has_index = False
    index_incr = 0
    def __init__(self, index, new_element):
        self.index = index
        self.new_element = new_element

class SetTuple(TupleOperation):
    def apply(self, current):
        assert False

class PopTuple(TupleOperation):
    has_index = True
    index_incr = -1
    def apply(self, current):
        return (*current[:self.index], *current[self.index+1:])

class ReplaceTuple(TupleOperation):
    has_index = True
    def apply(self, current):
        return (*current[:self.index], self.new_element, *current[self.index+1:])

class InsertTuple(TupleOperation):
    has_index = True
    index_incr = 1
    def apply(self, current):
        return (*current[:self.index], self.new_element, *current[self.index:])

class AppendTuple(TupleOperation):
    def apply(self, current):
        return (*current, self.new_element)


class TupleChange(common.LeafStateChange):
    def __init__(self, component, leaf_name, value_after, tuple_operation):
        super().__init__(component, leaf_name, value_after)
        self.tuple_operation = tuple_operation
        self.history = [tuple_operation]
        self.value_was_set = isinstance(tuple_operation, SetTuple)
        self.append_present = isinstance(tuple_operation, AppendTuple)

    def merge_in_rule(self, previous_update):
        # a rule has changed the same leaf twice, changes accumulate
        # self (new change) is one of the Tuple operations above, and so is previous
        # any sequence allowed
        # need to store sequence of operations but can forget after a "set-value"
        if previous_update is not None:
            # keep the original value (before rule invocation)
            self.value_before = previous_update.value_before

            if not self.value_was_set:
                self.history = previous_update.history + self.history
                self.value_was_set = previous_update.value_was_set

            self.append_present |= previous_update.append_present

    def name(self):
        return '.'.join(self.component.name) + '.' + self.leaf_name

    def merge_concurrent_rules(self, parallel_update):
        # two concurrent (clocked) rules have changed the same leaf twice
        # changes are only allowed if the end result is the same for either order of execution
        # for a tuple, this means:
        #   if one rule sets the value, the other is not permitted to do anything (so no merge called)
        #   if one rule appends to the tuple, the other rule is not permitted to append
        #   if one rule pops/inserts/replaces at index i, the other rule is not permitted to use index i
        # merging results in:
        #   parallel-update history added to self history
        #   preserve order
        #   if a pop at a lower index has happened, substract one from index of p/i/r
        #   if an insert at a lower index has happened, add one to index of p/i/r
        exc = common.NonDeterministicLeafChange
        exc.insist(
            not (self.value_was_set or parallel_update.value_was_set),
            f'Tuple {self.name()} does not support set from one rule and changes from another'
        )
        exc.insist(
            not (self.append_present and parallel_update.append_present),
            f'Tuple {self.name()} does not support append from two concurrent rules'
        )

        assert self.value_before == parallel_update.value_before

        for p_top in parallel_update.history:
            if p_top.has_index:
                for s_top in self.history:
                    if s_top.has_index:
                        exc.insist(
                            s_top.index != p_top.index,
                            f'Tuple {self.name()} does not support same-index mods from two concurrent rules'
                        )
                        if p_top.index > s_top.index:
                            p_top.index += s_top.index_incr
            self.value_after = TupleObject(self.component, self.leaf_name, p_top.apply(self.value_after))

        self.history += parallel_update.history


class TupleIndex(leaf.Leaf):
    index_stack = []

    @classmethod
    def stack_to_value(cls):
        stack = cls.index_stack
        return stack[-1] if stack else common.UnDefined

    @classmethod
    def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
        assert value is common.UnDefined
        return cls.stack_to_value()


@parameterise.Generic
def Tuple(entry_cls):
    frozen_entry_cls = entry_cls._dp_make_frozen_class()

    class TupleLeafState:
        _dp_class_cache_key = frozen_entry_cls
        param_entry_cls = entry_cls
        param_frozen_entry_cls = frozen_entry_cls
        entry_cls_is_leaf = issubclass(frozen_entry_cls, leaf.Leaf)

        @classmethod
        def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
            if value is common.UnSelected and allow_unsel:
                return value

            value = () if value is common.UnDefined else value
            fixed_value = []

            stack = TupleIndex.index_stack
            stack.append(0)
            try:
                for v in value:
                    if cls.entry_cls_is_leaf:
                        v_fixed = cls.param_entry_cls._dp_check_and_cast_including_undef(owner, name, v)
                    elif isinstance(v, cls.param_frozen_entry_cls):
                        v_fixed = v
                    elif isinstance(v, cls.param_entry_cls):
                        v_fixed = v.freeze()
                    else:
                        # try to build a frozen value from whatever we have been given
                        # will fail if not a dict and the entry-class is not able to accept it
                        if isinstance(v, dict):
                            v_fixed = cls.param_frozen_entry_cls(**v)
                        else:
                            v_fixed = cls.param_frozen_entry_cls(v)

                    fixed_value.append(v_fixed)
                    stack[-1] += 1
            finally:
                stack.pop(-1)

            return TupleObject(owner, name, fixed_value)

        @classmethod
        def _dp_instance_setattr_leaf_changes(cls, owner, name, current, value):
            # this needs to return a 1-tuple with a LeafStateChange in it
            # it calls check-and-cast
            # value is something castable to tuple, or a TupleOperation object
            if isinstance(value, TupleOperation):
                new_value = cls._dp_check_and_cast_including_undef(owner, name, value.apply(current))
                return (TupleChange(owner, name, new_value, value),)
            else:
                new_value = cls._dp_check_and_cast_including_undef(owner, name, value)
                return (TupleChange(owner, name, new_value, SetTuple(None, None)),)

    cls_name = f'Tuple_{entry_cls.__name__}'
    return leaf.Leaf.subclass(cls_name, TupleLeafState)
