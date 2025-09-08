''''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple BitVector type


A BitVector is a Leaf state element providing bit-access capability for integers

- as a static Leaf, it is immutable
- however, it has in-place modification capabilities
    - mutable if transient
    - replace leaf object in system state if static

- can have a defined bit-width, or be unbounded
- also provide field-location and array-indexer class

rules for defined width
- error to set to 1, any bit outside the width
- __str__ has value-independent width if defined-width, else as-wide-as-needed
- not an error to read bits outside the width; they are zero
- read from defined width gives defined-wdith result
- read from unlimited-width gives unlimited-width result

FIXME:
    FieldLocation should contain the implementations of __getitem__ and __setitem__
        for all bit-vector object types; then user can add others
        maybe define a __dp_bivector_getitem__
    Widthed bitvectors should have a concatenation operator or method
        return a transient (widthed if other also widthed?
        allow any integer type in the MSBs? (LSBs must know their own width)
        should LSBs be first LHS (logical) or RHS (visual)?
            could use matmul operator           a @ b
            offer a method                      a.extend_with(b)
            transient __init__ special case     BitVectorTransient[Width](a, b)
            transient __init__ hidden case      {a, b} or (a, b)
                set() matches verilog, but is unfortunately not ordered
                anyway, this doesn't work till assigned to a state element with known type
            a function                          Concatenate(a, b)
'''

from . import parameterise, leaf, state


@parameterise.Generic
def BitVector(width = None):
    if width is None:
        cls_name = 'BitVector'

        class BitVectorLeafState:
            _dp_class_cache_key = None

            @classmethod
            def _dp_check_and_cast(cls, owner, name, value):
                if owner is None:
                    return BitVectorTransientValue(value)
                else:
                    return BitVectorStaticValue(owner, name, value)

    else:
        # fixed-width bit-vector class
        assert isinstance(width, int) and width > 0
        cls_name = f'BitVector_{width}'

        class BitVectorLeafState:
            _dp_bitvector_width = width

            @classmethod
            def _dp_check_and_cast(cls, owner, name, value):
                if owner is None:
                    return BitVectorTransientValueWidthed(value, cls._dp_bitvector_width)
                else:
                    return BitVectorStaticValueWidthed(owner, name, value, cls._dp_bitvector_width)

            @classmethod
            def _dp_all_possible_values(cls):
                return range(2**cls._dp_bitvector_width)

    return leaf.Leaf.subclass(cls_name, BitVectorLeafState)


class FieldLocation:
    '''for indexing into a BitVector, like a python slice but with extra options

    my_bitvector[my_fieldlocation]
    my_bitvector[offset + my_fieldlocation]      moves the field by a number of bits
    my_bitvector[my_fieldlocation[index]]        moves the field by a multiple of its array-width
    '''
    def __init__(self, start, width = 1, array_width = None):
        self.start = start
        self.width = width
        self.array_width = width if array_width is None else array_width

    @property
    def stop(self):
        # returns the bit index after the last bit in this field
        return self.start + self.width

    @property
    def mask(self):
        # returns a mask with 1s in the bits that this field occupies
        return ((1 << self.width) - 1) << self.start

    @property
    def step(self):
        return 1

    def __add__(self, offset):
        return FieldLocation(
            start = self.start + offset,
            width = self.width,
            array_width = self.array_width,
        )

    def __getitem__(self, index):
        return FieldLocation(
            start = self.start + index * self.array_width,
            width = self.width,
            array_width = self.array_width,
        )


class BitVectorValueBase:
    def parse_slice(self, i):
        if isinstance(i, (FieldLocation, slice)):
            # range select, either a slice() or a FieldLocation
            start = 0 if i.start is None else int(i.start)
            stop = None if i.stop is None else int(i.stop)
            assert i.step in (1, None)
            return start, stop
        else:
            # single-bit select
            return int(i), int(i) + 1

    def __getitem__(self, i):
        start, stop = self.parse_slice(i)
        if stop is None:
            return self.transient(self.value >> start, start)
        else:
            mask = (1 << (stop - start)) - 1
            return self.transient((self.value >> start) & mask, start, stop)

    def setitem_new_value(self, i, value):
        int_value = int(value)
        start, stop = self.parse_slice(i)
        new_value = (int_value << start) | self[:start]
        if stop is not None:
            assert int_value < (1 << (stop - start)), \
                f'bit-vector value {value} too large for slice {start}:{stop}'
            new_value |= self.aligned(stop)
        return new_value

    def __repr__(self):
        return f'<BitVector:{self.value}>'

    # bit-vector operations returning transient BitVector
    def aligned(self, num_bits):
        return self.transient((self.value >> num_bits) << num_bits)

    def xor_reduce(self):
        return self.transient(self.value.bit_count() & 1, 0, 1)

    def or_reduce(self):
        return self.transient(0 if self.value == 0 else 1, 0, 1)

    def and_reduce(self, width = None):
        if width is None:
            if self.value & 1 == 0:
                return self.transient(1 if self == 0 else 0, 0, 1)
            else:
                return (self >> 1).and_reduce()
        else:
            all_one = (1 << width) - 1
            return self.transient(1 if self.value == all_one else 0, 0, 1)

    # in-place modification building on setitem
    def align(self, num_bits):
        self[:num_bits] = 0


class BitVectorTransientValue(BitVectorValueBase, state.MutableEmulatedIntegerBase):
    '''unlimited-width Bit-Vector

    Bit-Vector values are mutable, unlike normal Python integers, because
    they support __setitem__ for changing a subset of bits.

    In purple, leaf-state value objects must be immutable, so this means separate
    subclasses are needed for state and transient Bit-Vectors
    For symmetry with __setitem__, the other in-place operators also mutate the object
    '''
    def transient(self, value, start = None, stop = None):
        return BitVectorTransientValue(value)

    def __setitem__(self, i, value):
        self.value = self.setitem_new_value(i, value)

    def int_binary_op(self, other, op):
        '''if other can be an int, perform the op and return a BitVector
        otherwise, return whatever the raw-int operation does
        '''
        try:
            int_other = int(other)
        except Exception:
            int_other = None

        if int_other is None:
            return op(self.value, other)
        else:
            return self.transient(op(self.value, int_other))

    def int_unary_op(self, op):
        return self.transient(op(self.value))

    def inplace_op(self, other, op):
        try:
            self.value = op(self.value, int(other))
        except Exception:
            return NotImplemented
        return self


class BitVectorStaticValue(BitVectorValueBase, state.EmulatedIntegerBase):
    '''unlimited-width Bit-Vector

    Bit-Vector values are mutable, unlike normal Python integers, because
    they support __setitem__ for changing a subset of bits.

    In purple, leaf-state value objects must be immutable, so this means separate
    subclasses are needed for state and transient Bit-Vectors
    Modifications only happen during rule invocation, and
    get reported to the owner Record/Model

    Currently in purple all leaf state changes are immediately visible to the
    code making the change, so no requirement to request the current value from
    the running rule invocation
    '''
    def transient(self, value, start = None, stop = None):
        return BitVectorTransientValue(value)

    def __init__(self, owner, name, value):
        self.owner = owner
        self.name = name
        super().__init__(value)

    def __setitem__(self, i, value):
        setattr(self.owner, self.name, self.setitem_new_value(i, value))

    def int_binary_op(self, other, op):
        '''if other can be an int, perform the op and return a BitVector
        otherwise, return whatever the raw-int operation does
        '''
        try:
            int_other = int(other)
        except Exception:
            int_other = None

        if int_other is None:
            return op(self.value, other)
        else:
            return self.transient(op(self.value, int_other))

    def int_unary_op(self, op):
        return self.transient(op(self.value))


class BitVectorTransientValueWidthed(BitVectorTransientValue):
    '''prevents setting value to anything outside the (unsigned) limits of n bits

    does not object to slices outside the width of the bit-vector, provided
    the values are all-zero

    Note: leaf-class obtained by BitVector[23] has width in the class, but
    leaf-value objects store width in the object
    '''
    def __init__(self, value, width):
        self.width = width
        self.min_value = 0
        self.max_value = 1 << width
        self.check(value)
        super().__init__(value)

    def check(self, value):
        assert self.min_value <= value < self.max_value, f'{self.min_value} <= {hex(value)} < {hex(self.max_value)}'

    def __str__(self):
        hex_width = (self.width + 3) // 4
        return f'{self.value:0{hex_width}x}'

    def __repr__(self):
        return f'<BitVector[{self.width}]:{self}>'

    def transient(self, value, start = None, stop = None):
        start = 0 if start is None else start
        stop = self.width if stop is None else stop
        if stop <= start:
            assert value == 0
            return 0
        return BitVectorTransientValueWidthed(value, stop - start)

    def __setitem__(self, i, value):
        new_value = self.setitem_new_value(i, value)
        self.check(new_value)
        self.value = new_value

    def inplace_op(self, other, op):
        try:
            new_value = op(self.value, int(other))
            self.check(new_value)
            self.value = new_value
        except Exception:
            return NotImplemented
        return self

    def __invert__(self):
        'special case, clip to width'
        return self.transient((self.max_value - 1) & ~self.value)


class BitVectorStaticValueWidthed(BitVectorStaticValue):
    '''prevents setting value to anything outside the (unsigned) limits of n bits

    does not object to slices outside the width of the bit-vector, provided
    the values are all-zero

    Note: leaf-class obtained by BitVector[23] has width in the class, but
    leaf-value objects store width in the object

    because immutable, we only need checks in __init__
    '''
    def __init__(self, owner, name, value, width):
        assert 0 <= value < (1 << width)
        self.width = width
        super().__init__(owner, name, value)

    def __str__(self):
        hex_width = (self.width + 3) // 4
        return f'{self.value:0{hex_width}x}'

    def __repr__(self):
        return f'<BitVector[{self.width}]:{self.value}>'

    def transient(self, value, start = None, stop = None):
        stop = self.width if stop is None else stop
        start = 0 if start is None else start
        if stop <= start:
            assert value == 0
            return 0
        return BitVectorTransientValueWidthed(value, stop - start)

    def __invert__(self):
        'special case, clip to width'
        return self.transient(((1 << self.width) - 1) & ~self.value)
