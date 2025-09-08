'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple state types
'''

from . import common, leaf, parameterise

import enum
import operator


class Boolean(leaf.Leaf):
    @classmethod
    def _dp_check_and_cast(cls, owner, name, value):
        # require the value to be one of the following,
        # to avoid common python bug where most objects are "True"
        #   None
        #   castable to integer (includes True and False)
        #   a container, whose emptiness determines the boolean value
        if value is None:
            bool_value = False
        else:
            assert not isinstance(value, str)
            try:
                bool_value = bool(int(value))
            except (ValueError, TypeError):
                bool_value = bool(len(value))
        assert bool_value == bool(value)
        return bool_value

    @classmethod
    def _dp_all_possible_values(cls):
        return (True, False)


@parameterise.Generic
def Enumeration(*args, **kwargs):
    if len(args) == 1 and not kwargs and isinstance(args[0], enum.EnumType):
        the_enum_class = args[0]
    else:
        the_enum_class = enum.Enum(*args, **kwargs)

    class EnumLeafState:
        _dp_class_cache_key = the_enum_class
        enum_class = the_enum_class

        @classmethod
        def _dp_check_and_cast(cls, owner, name, value):
            assert value in cls.enum_class
            return value

        @classmethod
        def _dp_all_possible_values(cls):
            return cls.enum_class

        @classmethod
        def _dp_on_instantiation(cls, owner_class, name_in_owner):
            # put the actual Python enum class into any class where the enum is instantiated
            setattr(owner_class, name_in_owner, cls.enum_class)

    cls_name = 'Enum_FIXME'
    return leaf.Leaf.subclass(cls_name, EnumLeafState)


@parameterise.Generic
def Integer(*params):
    ''' optionally bounded integer leaf class

    normal Python: lower bound is inclusive and higher bound is exclusive
    parameter variants:
    - no parameters (ellipsis) or all-None means unbounded above and below
    - single positive int means 0 to that
    - single negative int means that to 0
    - 2 ints means lower to higher
    - Integer[None, i] or Integer[..., i] means -inf to i
    - Integer[i, None] or Integer[i, ...] means i to inf
    '''
    params = tuple(None if p is Ellipsis else p for p in params)
    if len(params) == 0:
        min_val = None
        max_val = None
    elif len(params) == 1:
        p = params[0]
        if p is None:
            min_val = None
            max_val = None
        elif p >= 0:
            min_val = 0
            max_val = p
        elif p < 0:
            min_val = p + 1
            max_val = 1
    elif len(params) == 2:
        p,q = params
        if p is None or q is None:
            min_val,max_val = p,q
        elif p > q:
            max_val,min_val = q,p
        else:
            min_val,max_val = p,q

    class IntegerLeafState:
        _dp_class_cache_key = min_val, max_val
        param_bounds = min_val, max_val

        @classmethod
        def _dp_check_and_cast(cls, owner, name, value):
            rv = int(value)
            pmin, pmax = cls.param_bounds
            assert pmin is None or pmin <= rv
            assert pmax is None or pmax > rv
            return rv

        @classmethod
        def _dp_all_possible_values(cls):
            assert None not in cls.param_bounds, 'unbounded integer has infinite values'
            return range(*cls.param_bounds)

    def bound(v, i):
        return (i if v is None else str(v)).replace('-', 'n')
    cls_name = f'Integer_{bound(min_val, "-inf")}_{bound(max_val, "inf")}'

    return leaf.Leaf.subclass(cls_name, IntegerLeafState)


@parameterise.Generic
def Constant(val):
    class ConstantLeafState:
        _dp_initial_value = val
        param_val = val

        @classmethod
        def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
            if value is common.UnSelected and allow_unsel:
                return value
            else:
                assert value == cls.param_val
                return cls.param_val

        @classmethod
        def _dp_all_possible_values(cls):
            return [cls.param_val]

    cls_name = 'Constant_FIXME'
    return leaf.Leaf.subclass(cls_name, ConstantLeafState)


@parameterise.Generic
def ModuloInteger(modulus):
    assert isinstance(modulus, int) and modulus > 0
    cls_name = f'ModuloInteger_{modulus}'

    class ModuloIntegerLeafState:
        param_modulus = modulus

        @classmethod
        def _dp_check_and_cast(cls, owner, name, value):
            return ModuloIntegerValue(value, cls.param_modulus)

        @classmethod
        def _dp_all_possible_values(cls):
            return range(cls.param_modulus)

    return leaf.Leaf.subclass(cls_name, ModuloIntegerLeafState)


class EmulatedIntegerBase:
    ''' Leaf state types may create objects of a subtype

    purpose is to allow the integer objects to have some different behaviour from normal Python int

    normally immutable, in which case the same class can be used for transients
    and for leaf state elements
    '''
    def __init__(self, value):
        self.value = int(value)

    # symmetrical binary operators usually return an emulated-integer object
    def __add__(self, other, op = operator.add):
        return self.int_binary_op(other, op)

    def __sub__(self, other, op = operator.sub):
        return self.int_binary_op(other, op)

    def __mul__(self, other, op = operator.mul):
        return self.int_binary_op(other, op)

    def __or__(self, other, op = operator.or_):
        return self.int_binary_op(other, op)

    def __and__(self, other, op = operator.and_):
        return self.int_binary_op(other, op)

    def __xor__(self, other, op = operator.xor):
        return self.int_binary_op(other, op)

    def __floordiv__(self, other, op = operator.floordiv):
        return self.int_binary_op(other, op)

    def __pow__(self, other, op = operator.pow):
        return self.int_binary_op(other, op)

    def __mod__(self, other, op = operator.mod):
        return self.int_binary_op(other, op)

    def __lshift__(self, other, op = operator.lshift):
        return self.int_binary_op(other, op)

    def __rshift__(self, other, op = operator.rshift):
        return self.int_binary_op(other, op)

    # right-side binary operators return what the LHS chooses
    def rhs_binary_op(self, other, op):
        return op(other, self.value)

    def __radd__(self, other, op = operator.add):
        return self.rhs_binary_op(other, op)

    def __rsub__(self, other, op = operator.sub):
        return self.rhs_binary_op(other, op)

    def __rmul__(self, other, op = operator.mul):
        return self.rhs_binary_op(other, op)

    def __ror__(self, other, op = operator.or_):
        return self.rhs_binary_op(other, op)

    def __rand__(self, other, op = operator.and_):
        return self.rhs_binary_op(other, op)

    def __rxor__(self, other, op = operator.xor):
        return self.rhs_binary_op(other, op)

    def __rfloordiv__(self, other, op = operator.floordiv):
        return self.rhs_binary_op(other, op)

    def __rpow__(self, other, op = operator.pow):
        return self.rhs_binary_op(other, op)

    def __rmod__(self, other, op = operator.mod):
        return self.rhs_binary_op(other, op)

    def __rlshift__(self, other, op = operator.lshift):
        return self.rhs_binary_op(other, op)

    def __rrshift__(self, other, op = operator.rshift):
        return self.rhs_binary_op(other, op)

    # binary operators returning something other than a transient emulated-integer object
    def nonint_binary_op(self, other, op):
        try:
            return op(self.value, int(other))
        except Exception:
            return NotImplemented

    def __truediv__(self, other, op = operator.truediv):
        return self.nonint_binary_op(other, op)

    def __lt__(self, other, op = operator.lt):
        return self.nonint_binary_op(other, op)

    def __le__(self, other, op = operator.le):
        return self.nonint_binary_op(other, op)

    def __gt__(self, other, op = operator.gt):
        return self.nonint_binary_op(other, op)

    def __ge__(self, other, op = operator.ge):
        return self.nonint_binary_op(other, op)

    def __eq__(self, other, op = operator.eq):
        return self.nonint_binary_op(other, op)

    def __ne__(self, other, op = operator.ne):
        return self.nonint_binary_op(other, op)

    # symmetrical unary operators (return an emulated int)
    def __neg__(self, op = operator.neg):
        return self.int_unary_op(op)

    def __pos__(self, op = operator.pos):
        return self.int_unary_op(op)

    def __abs__(self, op = operator.abs):
        return self.int_unary_op(op)

    def __invert__(self, op = operator.inv):
        return self.int_unary_op(op)

    # unary operators returning something other than a transient emulated-integer object
    def __hash__(self):
        return self.value.__hash__()

    def __index__(self):
        return self.value  # implicitly defines conversions to int/float/complex

    def __bool__(self):
        return self.value.__bool__()

    def __str__(self):
        return self.value.__str__()

    def __repr__(self):
        return f'<EmulatedInt:{self.value}>'

    def __format__(self, spec):
        return self.value.__format__(spec)

    def bit_length(self):
        return self.value.bit_length()

    def bit_count(self):
        return self.value.bit_count()

    # in-place modifications not supported (x += 1 will work using non-in-place binary op)


class ModuloIntegerValue(EmulatedIntegerBase):
    def __init__(self, value, modulus):
        self.modulus = modulus
        super().__init__(int(value) % modulus)

    def int_binary_op(self, other, op):
        '''if other can be an int, perform the op and return a ModuloInteger
        otherwise, return whatever the raw-int operation does
        '''
        try:
            int_other = int(other)
        except Exception:
            int_other = None

        if int_other is None:
            return op(self.value, other)
        else:
            return ModuloIntegerValue(op(self.value, int_other), self.modulus)

    def int_unary_op(self, op):
        return ModuloIntegerValue(op(self.value), self.modulus)

    def __repr__(self):
        return f'<IntMod({self.modulus}):{self.value}>'


class MutableEmulatedIntegerBase(EmulatedIntegerBase):
    ''' Leaf state types may create objects of a subtype

    purpose is to allow the integer objects to have some different behaviour from normal Python int

    when mutable, eg for BitVector, can only be used for transient objects
    '''
    def __iadd__(self, other, op = operator.iadd):
        return self.inplace_op(other, op)

    def __isub__(self, other, op = operator.isub):
        return self.inplace_op(other, op)

    def __imul__(self, other, op = operator.imul):
        return self.inplace_op(other, op)

    def __ifloordiv__(self, other, op = operator.ifloordiv):
        return self.inplace_op(other, op)

    def __imod__(self, other, op = operator.iadd):
        return self.inplace_op(other, op)

    def __ipow__(self, other, op = operator.ipow):
        return self.inplace_op(other, op)

    def __ilshift__(self, other, op = operator.ilshift):
        return self.inplace_op(other, op)

    def __irshift__(self, other, op = operator.irshift):
        return self.inplace_op(other, op)

    def __iand__(self, other, op = operator.iand):
        return self.inplace_op(other, op)

    def __ixor__(self, other, op = operator.ixor):
        return self.inplace_op(other, op)

    def __ior__(self, other, op = operator.ior):
        return self.inplace_op(other, op)
