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

from . import common, metaclass, parameterise, record, model, leaf
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

    def __getitem__(self, index):
        if isinstance(index, slice):
            as_tuple = tuple(self[i] for i in self._dp_array_slice_range(index))
            return Array[len(as_tuple), self._dp_array_type](as_tuple)
        else:
            return self.__getattribute__(self._dp_array_2attrname(index))

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            for i,new_v in zip(self._dp_array_slice_range(index), value):
                self[i] = new_v
        else:
            self.__setattr__(self._dp_array_2attrname(index), value)

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

    def fix_index(i, array_length = array_length):
        return (array_length + i) if i < 0 else i

    def slice_range(index,
        array_length = array_length,
        fix_index = fix_index,
    ):
        if index.step is None or index.step > 0:
            start = 0 if index.start is None else fix_index(index.start)
            stop = array_length if index.stop is None else fix_index(index.stop)
            step = 1 if index.step is None else index.step
        else:
            start = (array_length - 1) if index.start is None else fix_index(index.start)
            stop = -1 if index.stop is None else fix_index(index.stop)
            step = index.step
        return range(start, stop, step)

    def to_attrname(index,
        array_length = array_length,
        int_width = len(str(array_length - 1)),
        fix_index = fix_index,
    ):
        fixed_index = fix_index(index)
        if fixed_index >= array_length or fixed_index < 0:
            raise IndexError
        return f'_{fixed_index:0{int_width}}'

    def to_index(attrname):
        return int(attrname.replace('_', ''))

    class TheArray(ArrayBase, purple_base):
        _dp_array_is_model = is_model
        _dp_array_length = array_length
        _dp_array_type = cls
        _dp_array_2attrname = staticmethod(to_attrname)
        _dp_array_2index = staticmethod(to_index)
        _dp_array_slice_range = staticmethod(slice_range)

        for i in range(array_length):
            metaclass.add_state(to_attrname(i), cls)

    return TheArray

# break circular import dependency
metaclass.PurpleComponentMetaClass.generic_array = Array


array_index_for_initial_value = []

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
    calling is done thus: self.a_method[i](etc)

    can take a depth parameter, or not

    can be iterated over, for binding eg to an array of Port,
        but only within a zip() if there's no finite depth
    '''
    length = None

    def __class_getitem__(cls, array_length):
        return type(cls)(f'HandlerArray_{array_length}', (cls,), dict(length = array_length))

    def __init__(self, the_method):
        self.the_method = the_method
        self.name = (the_method.__name__,)

    def __get__(self, owner, owner_cls):
        return self.Got(self, owner)

    class Got:
        def __init__(self, array, owner):
            self.array = array
            self.owner = owner
            self.length = array.length

        def __getitem__(self, index):
            if self.length is None or 0 <= index < self.length:
                return self.CallMe(self.owner, self.array, index)
            else:
                raise IndexError

        class CallMe:
            def __init__(self, owner, array, index):
                self.owner = owner
                self.index = index
                self.the_method = array.the_method

            def __call__(self, *a, **ka):
                return self.the_method(self.owner, self.index, *a, **ka)
