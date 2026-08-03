'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple transient and static array types

An array is just syntactic sugar for a level of hierarchy

FIXME: add ability to set array-in-record/model from iterable
eg
    myrecord.thearray = [1,2,3,4]

FIXME: add ability to iterate over an Array class
eg
    MyArray = (10 * MyRecord)
    for i in MyArray.indices(): do_something
    for i in MyArray.keys(): do_something

FIXME:
    more tests of ArrayIndex eg in transient copy/copy record to/from model
    note that unexpected behaviour may occur when copying an array with ArrayIndex
    between records/models with different depths of array nesting or copying out
    of an array
    eg for transients some copying is shallow and ArrayIndex will reflect the source
'''

from . import common, metaclass, parameterise, record, model, leaf, state
import inspect


class ArrayBase:
    # for array-index
    _dp_key_stack = []

    def __init__(self, iterable = (), **changes):
        if self._dp_array_is_model:
            assert iterable == (), 'cannot create static array outside elaboration'
            assert changes == {'is_top':False}, 'cannot create static array outside elaboration'
        else:
            for i,v in enumerate(iterable):
                changes[self._dp_array_2attrname(i)] = v

        super().__init__(**changes)

    def __len__(self):
        return self._dp_array_length

    def __add__(self, other):
        # array concatenation
        assert not self._dp_array_is_model, 'concatenated arrays must be transient'
        assert self._dp_array_type == other._dp_array_type, 'concatenated arrays must have the same element type'
        combined_len = self._dp_array_length + other._dp_array_length
        return Array[combined_len, self._dp_array_type](tuple(self) + tuple(other))

    @classmethod
    def _dp_array_2attrname(cls, index):
        # support negative indices
        while index < 0:
            index += cls._dp_array_length
        if index >= cls._dp_array_length:
            raise IndexError
        return f'_{index:0{cls._dp_array_idx_width}}'

    @classmethod
    def _dp_array_2index(cls, attrname):
        return int(attrname.replace('_', ''))

    def _dp_array_adjust_index(self, index):
        # for Pipeline and FIFO derived classes
        return index

    def __getitem__(self, index):
        if isinstance(index, slice):
            slice_range = range(self._dp_array_length)[index]
            as_tuple = tuple(self[i] for i in slice_range)
            return Array[len(as_tuple), self._dp_array_type](as_tuple)
        else:
            adj_index = self._dp_array_adjust_index(index)
            return self.__getattribute__(self._dp_array_2attrname(adj_index))

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            slice_range = range(self._dp_array_length)[index]
            for i,new_v in zip(slice_range, value):
                self[i] = new_v
        else:
            adj_index = self._dp_array_adjust_index(index)
            self.__setattr__(self._dp_array_2attrname(adj_index), value)

    @classmethod
    def _dp_merge_initial_value(cls, owner_initial_value, base_initial_value):
        ''' makes the initial values for an instance of cls in owner-cls

        called repeatedly, for every base of the owner class where the instance is declared
            because each instance can override the initial values or even change the element type

        owner_initial_value is created here and is obtained from the superclass merge-initial-values

        base_initial_value can be
            if no overrides are given, unique-object
            if selective overrides are given, dict
            a new transient record object wholly replacing the owner-initial-value
            undef wholly replacing the owner-initial-value
            an iterable other than an array transient => convert to dict of changes for model compatibility
        '''
        if not (
            base_initial_value in (common.UniqueObject, common.UnDefined, common.UnSelected)
            or isinstance(base_initial_value, dict)
            or isinstance(base_initial_value, cls)
        ):
            base_initial_value = {cls._dp_array_2attrname(i):v for i,v in enumerate(base_initial_value)}

        return super()._dp_merge_initial_value(owner_initial_value, base_initial_value)

    @classmethod
    def _dp_transient_init(cls, default, changes, owner, name):
        '''called by Record() when creating a new transient containing a state element of type cls

        changes is one of
            an object of type cls
                return it (shallow copy)
            a dict
                apply changes sparsely to copy of default
            UniqueObject (means no changes)
                same as dict but ultimate in sparseness
            UnDefined
                copy default replacing everything with undef
            some iterable
                convert to a dict
        '''
        if not (
            changes in (common.UniqueObject, common.UnDefined)
            or isinstance(changes, dict)
            or isinstance(changes, cls)
        ):
            changes = {cls._dp_array_2attrname(i):v for i,v in enumerate(changes)}

        return super()._dp_transient_init(default, changes, owner, name)


@parameterise.Generic
def Array(array_length, cls):
    is_model = issubclass(cls, model.Model)
    purple_base = model.Model if is_model else record.Record

    class TheArray(ArrayBase, purple_base):
        _dp_array_is_model = is_model
        _dp_array_length = array_length
        _dp_array_type = cls
        _dp_array_idx_width = len(str(array_length - 1))

        for i in range(array_length):
            class Element(metaclass.AddToState(e_name = f'_{i:0{_dp_array_idx_width}}', ArrayType = cls)):
                e: ArrayType

    return TheArray


class ArrayIndexBase(leaf.Leaf):
    class InitialValue:
        # this class is used only to provide some protection against runtime modification
        def __init__(self, iv):
            self.iv = iv

    _dp_initial_value = InitialValue(None)

    @classmethod
    def _dp_copy_initial_value(cls, source):
        # assumes that leaf sources are immutable (do not need copy)
        int_stack = tuple(int(i.replace('_', '')) for i in ArrayBase._dp_key_stack)
        return cls.InitialValue(cls.convert_index_stack(int_stack))

    @classmethod
    def _dp_all_possible_values(cls):
        # should evaluate to the default (the index) when the array is built
        return [common.UnDefined]

    @classmethod
    def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
        if value is common.UnSelected and allow_unsel:
            return value
        else:
            assert isinstance(value, cls.InitialValue)
            return value.iv


class ArrayIndex(ArrayIndexBase):
    # replace this method to convert from a tuple of array indices
    # into something that will be set as an attribute of the owning Record or Model
    @classmethod
    def convert_index_stack(cls, index_stack):
        return index_stack[-1]


@parameterise.Generic
def FromArrayIndex(converter_function):
    ''' easy creation of an ArrayIndex with any user-supplied conversion of the index

    if expected to be in a multi-dimensional array, this function
    needs to not fail when (reduced-dimensional) element records are declared
    '''
    num_args = len(inspect.signature(converter_function).parameters)

    class ModifiedArrayIndex(ArrayIndexBase):
        @classmethod
        def convert_index_stack(cls, index_stack, cv = converter_function, num_args = num_args):
            zeros = tuple(0 for _ in range(num_args - len(index_stack)))
            extended_is = (*zeros, *index_stack)
            return cv(*extended_is)
    return ModifiedArrayIndex


class HandlerArray:
    '''decorator for converting a method into a array type

    decorates a method of the form:  def a_method(self, index, etc):

    getitem has the effect of inserting a new method into the class being
        parsed, which method is bound to the index
    this means that port binding can look for "function" and does not need to
        know about HandlerArray

    can be called
        through a bound port
        as declared self.a_method(index, etc)
        as an array of methods self.a_method[i](etc)
    '''
    def __init__(self, the_method):
        self.the_method = the_method
        self.method_name = the_method.__name__

    class BoundToOwner:
        def __init__(self, hdlr_array, owner, index):
            self.hdlr_array = hdlr_array
            self.owner = owner
            self.index = index

        def __getitem__(self, index):
            return type(self)(self.hdlr_array, self.owner, index)

        def __call__(self, *a, **ka):
            if self.index is common.UniqueObject:
                return self.hdlr_array.the_method(self.owner, *a, **ka)
            else:
                return self.hdlr_array.the_method(self.owner, self.index, *a, **ka)

    def __get__(self, owner, owner_cls):
        if owner is None:
            self.owner_cls = owner_cls
            return self
        else:
            return self.BoundToOwner(self, owner, common.UniqueObject)

    def __getitem__(self, index):
        def handler(owner, *a, index = index, hdlr_array = self, **ka):
            bound_handler = getattr(owner, hdlr_array.method_name)
            return bound_handler(index, *a, **ka)
        handler.__name__ = f'{self.method_name}_dp_arrayhandler_{index}'
        setattr(self.owner_cls, handler.__name__, handler)
        return handler


@parameterise.Generic
def Pipeline(array_cls):
    class PipelineArray(array_cls):
        end_index: state.ModuloInteger[array_cls._dp_array_length] = 0

        def _dp_array_adjust_index(self, index):
            # allows user to look at content in-order
            return self.end_index + index

        def __eq__(self, other):
            if other._dp_array_length != self._dp_array_length:
                return False
            for i in range(self._dp_array_length):
                if self[i] != other[i]:
                    return False
            return True

        def current_output(self):
            return self[0]

        def advance_pipeline(self, new_value):
            self[0] = new_value
            self.end_index += 1

    return PipelineArray


RdEmptyFIFO = common.PurpleException.subclass('RdEmptyFIFO')
WrFullFIFO = common.PurpleException.subclass('WrFullFIFO')

@parameterise.Generic
def FIFO(array_cls, read_empty_is_error = False, write_full_is_error = False):
    class FIFO(array_cls):
        _dp_fifo_read_empty = RdEmptyFIFO if read_empty_is_error else common.GuardFailed
        _dp_fifo_write_full = WrFullFIFO if write_full_is_error else common.GuardFailed

        def _dp_array_adjust_index(self, index):
            # allows user to peek at content in-order: index is from 0 to load-1
            common.ReadUnDefined.insist(index < self.load(), 'attempt to access unoccupied part of FIFO')
            return (self.rd_index + index) % self._dp_array_length

        rd_index: state.ModuloInteger[2 * array_cls._dp_array_length] = 0
        wr_index: state.ModuloInteger[2 * array_cls._dp_array_length] = 0

        def full(self):
            return self.rd_index == self.wr_index + self._dp_array_length

        def empty(self):
            return self.rd_index == self.wr_index

        def load(self):
            return self._dp_array_length if self.full() else (self.wr_index - self.rd_index)

        def peek(self):
            self._dp_fifo_read_empty.insist(not self.empty())
            return self[0]

        def pop(self):
            rv = self.peek()
            self.rd_index += 1
            return rv

        def push(self, new_value):
            self._dp_fifo_write_full.insist(not self.full())
            self.wr_index += 1
            self[self.wr_index - 1 - self.rd_index] = new_value

    return FIFO
