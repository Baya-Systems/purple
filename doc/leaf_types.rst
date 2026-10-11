..
    MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>


Purple Leaf Types
--------------------

The following *Leaf* types are provided as part of *Purple*.
All *Model* state is ultimately held in leaf elements.

Additional types can be added as required.


Constant
=================================

Generic type, taking one parameter which can be any Python object.
The state element can only take that object as its value, nothing else.

It is strongly recommended not to put mutable Python objects into constants,
and if this is unavoidable it is not allowed to modify them.
Such modifications are not prevented by Purple, but will cause simulation
semantics to be broken and behaviour to be non-deterministic.

Initial values do not need to be set; the default is the constant value
and UnDefined is not used.


..  code::  python

    class My_Model(purple.Model):
        constant_integer_345: purple.Constant[345]
        constant_tuple: purple.Constant[(3, 4, 5)]


Boolean
=================================

Can take the values *True* and *False*, or be *UnDefined*.
Default initial value is UnDefined.

Automatically cast from any Python object that Python knows how to cast
to True/False.


..  code::  python

    class My_Model(purple.Model):
        flag_a: purple.Boolean = True
        flag_b: purple.Boolean   # defaults to UnDefined

        def rule_method(self):
            self.flag_a = False
            self.flag_b = ['a', 'list', 'of', 'strings']
            assert self.flag_b is True, 'passes'


Enumeration
=================================

Generic type, taking a standard Python enum.Enum class as parameter.
Can take any value from that Enum, or UnDefined.
Default initial value is UnDefined.


..  code::  python

    import enum

    My_Enum = enum.Enum('My-Enum', 'A B C D')

    class My_Model(purple.Model):
        enum_a: purple.Enumeration[My_Enum] = My_Enum.B


Integer
=================================

Generic type, taking one or two parameters.
Parameter values that are *None* or *Ellipsis* ("...") are interpreted as infinity
or negative-infinity.

If only one parameter is provided:

* if None/Ellipsis, this is an unrestricted Python integer
* if parameter is a non-negative integer, values can be from 0 to that number minus 1,
  like a Python range
* otherwise parameter must be a negative integer and values can be from that number
  plus one to 0

If 2 parameters are provided, values can be from the smaller to the larger minus 1.
Both must be integers or None/Ellipsis.

Default initial value is UnDefined.


..  code::  python

    class My_Model(purple.Model):
        int_a: purple.Integer[...] # any integer
        int_b: purple.Integer[6]   # integers in range(6)
        int_c: purple.Integer[6, 12]   # integers in range(6, 12)
        int_d: purple.Integer[-6]   # integers in range(-5, 0)
        int_e: purple.Integer[..., 7]   # integers in range(-infinity, 7)
        int_f: purple.Integer[7, ...]   # integers in range(7, infinity)


ModuloInteger
=================================

Generic type, taking one parameter which must be an integer.
Default initial value is UnDefined.

Can be cast from any integer value, and will result in an integer-like
object between 0 and the generic parameter minus 1.

ModuloInteger objects can be transient as well as static model state variables,
and modulo-arithmetic is supported for transients.


..  code::  python

    class My_Model(purple.Model):
        modulo_counter: purple.ModuloInteger[10]

        def rule_method(self):
            if condition:
                self.modulo_counter += 1
                # will go from 1->2, 2->3, etc but 9->0
            else:
                self.modulo_counter = 25
                # will go to 5


BitVector
=================================

Generic type, taking one parameter which must be an integer, indicating
the width of the BitVector.
This parameter is optional: if set to None then the BitVector has infinite width.
Default initial value is UnDefined.

Can be cast from any integer value that is between 0 and 2**width - 1, and will
result in an integer-like object with that value.

The following features are available for BitVector objects:

*   ``aligned(self, num_bits)``
    returns a BitVector copy except the lowest num_bits are all zero
*   ``align(self, num_bits)``
    sets the lowest num_bits to zero
*   ``xor_reduce(self)``
    returns 1 or 0 depending on number of 1s in the BitVector (parity)
*   ``or_reduce(self)``
    returns 1 or 0 depending on whether there are any 1s in the BitVector
*   ``and_reduce(self)``
    returns 1 or 0 depending on whether there the BitVector is all-1s (only when width is finite)
*   ``__getitem__(self, index_or_slice_or_fieldlocation)``
    returns a BitVector copy of the specified sub-vector
*   ``__setitem__(self, index_or_slice_or_fieldlocation, value)``
    sets the specified sub-vector to the value

Slices used to select sub-vectors follow normal Python-style, so the lower bit index
comes first and the higher comes second, and the higher is the bit index above the
last bit selected (slice.stop is not part of the selection).
Unspecified start and stop are allowed; start defaults to bit 0, stop to the BitVector width.

A class *FieldLocation* is provided which provides help for accessing fields
within a BitVector.
A field-location may be used in place of a conventional Python slice, in __getitem__
or __setitem__.
A field-location has a start and a width and also an array-width, and can be

* added to, to shift it up or down the BitVector preserving its width
* indexed, to shift it by a multiple of its array-width, this treating the BitVector as
  an array of sub-vectors

BitVector objects can be transient as well as static model state variables,
and the various bit operations described above are supported for transients.


..  code::  python

    class My_Model(purple.Model):
        bv_a: purple.BitVector[12]

        def rule_method(self):
            self.bv_a = 0x345
            self.bv_a[4:8] = 0xd
            assert self.bv_a == 0x3d5, 'passes'
            assert self.bv_a[:4] == 0x3, 'passes'

            fl = purple.FieldLocation(start = 1, width = 2, array_width = 4)
            assert self.bv_a[fl] == self.bv_a[1:3], passes
            assert self.bv_a[fl + 3] == self.bv_a[4:6], passes
            assert self.bv_a[fl[1]] == self.bv_a[5:7], passes
            assert self.bv_a[fl[2]] == self.bv_a[9:11], passes


Counter
=================================

Generic type, taking one parameter which must be a positive integer.
Values between zero and that integer minus 1 are possible.
Default initial value is UnDefined.

An optional second parameter exists, which determines the counter
behaviour on attempting to set a value out of bounds.
The options are to raise an exception, or to guard the current rule so that
it is treated as "cannot-happen, therefore doesn't-happen".

Counter objects cannot be transient, only static model-state.

The purpose of Counter is that it supports concurrent modification from
multiple rules.
Only clocked rules can be concurrent, therefore Counter does not add any
useful features for atomic rule models.
However, Counter is compatible with atomic rules.

If concurrent clocked rules modify a Counter:

* the only supported concurrent operations are to add (or subtract) a value
  from the Counter.
  These operations must use Python's in-place operators "+=" or "-="
* if any rule does any other Counter modification (eg sets its value) then it
  is an error for other rules to modify the Counter concurrently
* all rules adding to the Counter must see their local modification remain
  within bounds, otherwise error or that rule is guarded
* the combination of all concurrent additions to the Counter must also remain
  within bounds, otherwise all rules touching the Counter are guarded


..  code::  python

    class My_Model(purple.Model):
        counter: purple.Counter[10] = 5

        def clocked_method_a(self):
            if new_thing:
                self.counter += 1

        def clocked_method_b(self):
            if thing_finished:
                self.counter -= 1


Tuple
=================================

Generic type, taking one parameter which must be a Purple *Leaf*, *Record* or *Union* type.
This will create a model state element similar to a Python tuple whose elements are
limited to one type and which is immutable except within Purple rule invocation.

Tuple is a leaf state type with unbounded storage requirement; any number of elements
can be inserted into it.
Therefore it is not appropriate for modelling hardware components.
It is useful for storing state in testbenches and checkers.

Default initial value is an empty Tuple.

The following features are available for Tuple objects:

*   ``pop(self, index = 0)``
    remove an element from the Tuple and return it
*   ``replace(self, index, value)``
    return the element at the index, and replace it with the new value
*   ``insert(self, index, value)``
    insert a new value into the Tuple at the specified index
*   ``append(self, value)``
    insert a new value into the Tuple at the end

Normal reading of Tuple elements by indexing (square brackets), including making
sub-Tuples from slices.

Tuple objects cannot be transient, only static model-state.

Tuple supports concurrent modification from multiple rules.
Only clocked rules can be concurrent, but Tuple features are also
useful for atomic rule models.

If concurrent clocked rules modify a Tuple:

* if any rule sets the entire Tuple to a value, then it
  is an error for other rules to modify the Tuple concurrently
* if any rule appends a value to the Tuple, then it
  is an error for other rules to append values to the Tuple concurrently
* no 2 rules may insert or replace or pop at the same index concurrently
* in general, concurrent operations are only allowed if all orders of
  sequential invocation of the rules would product the same result


..  code::  python

    class My_Model(purple.Model):
        my_tuple: purple.Tuple[purple.Integer[20]] = (1, 2, 3, 4)

        def clocked_method_a(self):
            if new_number > self.my_tuple[-1]:
                self.tuple.append(new_number)

        def clocked_method_b(self):
            if old_number > self.my_tuple[0]:
                self.my_tuple.pop(0)


StimulusQueue
=================================

A highly specialised type for helping use of atomic-rule models in verification
of implementations of hardware components.

See verification.
