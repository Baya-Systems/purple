..
    MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>


Unions
------------------

There are two motivations for *Unions*:

* simple way to create a more complex *Leaf* class

  * for example a 10-bit integer where bit 8 is always zero

    ``Restricted_Int = Integer[0, 256] | Integer[512, 768]``

* creation of message classes where different types of sub-message are carried in the same field

  ..    code::  python

        Opcode = enum.Enum('Opcode', 'Rd Wr')

        class Rd_Request:
            addr: Integer[...]

        class Wr_Request:
            addr: Integer[...]
            data: Integer[...]

        class Request:
            opcode: Enumeration[Opcode]
            request: Rd_Request | Wr_Request

A union can contain a mixture of *Record* and *Leaf* types.
This may have been a bad choice for Purple, as it adds significantly to complexity and testing.

Unions are created using the OR (``|``) operator on record, leaf or other union classes.

The order of classes used to create the union determines the preferred option class and hence the
default initial value.
Unions with different option class order but the same option classes evaluate equal to each other.

Objects whose class is a union class should never exist; the object, whether part of static model
state or a transient, is created by one of the union's option classes.

When a union is defined as part of static model state, all the record classes within it get
elaborated, so permanent objects exist for all of them.
However, only one of these objects is *selected* at any time.
The unselected ones have all their leaf state set to the special value *UnSelected*.

This means that there is an implicit state variable for a system containing a union: which option
class is selected.
It is definitely not the intention that model behaviour code attempt to use this information.
For example in the example above, code could try ``if getattr(my_request, 'data', UnSelected) is UnSelected:``
to determine if ``my_request`` is a read or a write.
This would not be an intuitive model of anything useful.
The "correct" alternative would be ``if my_request.opcode is Opcode.Rd:``

A union cannot be an option class of another unions; this is equivalent to a union with the combined
option classes of both.

Unions can have *Record* option classes containing further unions.
