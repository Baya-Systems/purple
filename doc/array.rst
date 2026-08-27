..
    MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>


Purple Arrays
-----------------------------------

Within a *Record* or a *Model*, state elements can be organised in arrays.
An array is itself a *Record* or a *Model* and contains a collection of elements of the same type.

Arrays are in fact syntactic sugar for normal hierarchical state where the state
element names are "_0", "_1", etc.
This is the deafult mapping of index to element name; other mappings can be defined if desired.

Arrays are created either by using square brackets or more simply by using the "star" multiplication
operator.

Array initial values can be passed as any interable.

Inside an array, it is possible to set a state variable to the array index value.


..  code::  python

    array_length = 20

    class MyArrayElement(Record):
        flag: Boolean
        index_in_array: ArrayIndex

    class Message(Record):
        # the below are equivalent
        some_flags: array_length * Boolean
        more_flags: Array[20, Boolean]

        # initial values: index_in_array will be [0,1,2,3,4]
        my_array: (5 * MyArrayElement) = (dict(flag = True) for i in range(5))


*Port* binding and arrays can be defined in different ways:

* an individual port from an array-of-ports can be bound to another port or to a handler
* a slice of ports from an array-of-ports can be bound to a slice of another port-array or to a
  slice of a *HandlerArray*
* a slice of a sub-component array, where the sub-component contains a port, can be bound to
  a handler-array-slice or a port-array-slice


..  code::  python

    array_length = 20

    class Source(Model):
        output: Port[Boolean]

    class Destination(Model):
        # single port to single handler
        input: Port[Boolean] >> input_handler

        def input_handler(self, b: Boolean):
            self.print('destination received:', b)

    class Top(Model):
        sources: (5 * Source)
        destinations: (5 * Destination)
        top_inputs: (5 * Port[Boolean])

        @HandlerArray
        def handler(self, index, b: Boolean):
            self.print('top received:', b)

        # different binding options: Note they are not mutually compatible

        entire_array_to_entire_array: sources[:].output >> destinations[:].input

        loop: [
            sources[0:4].output >> destinations[1:5].input,
            sources[-1].output >> destinations[0].input,
        ]

        top_handlers: top_inputs[:] >> handler[:]

        one_port_special_case: top_inputs[2] << sources[3].output

        one_port_handler: destinations[4].input >> handler[1]


Special types of array are available:

* ``Pipeline[<length> * Type]`` is an efficient implementation of a fixed-length pipeline.
* ``FIFO[<length> * Type]`` is a FIFO buffer
