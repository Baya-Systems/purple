..
    MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>


Setting Initial Values for State Objects
-----------------------------------------------------

Special Values
=========================

A *Leaf* type has a restricted set of values that it can take.

Two built-in values are usually added to this set when the leaf type is declared:

* *UnDefined*, used to indicate that the leaf object is a "don't-care" in the current system state
* *UnSelected*, used to indicate leaves within a record that is part of a *Union*, when
  that record is not currently the type of the union object

It is an error to read an object that is undefined, or to test it for undefined-ness.

It may be possible to test whether an object is unselected, but this is not good practice because
does not represent any other implementation of the system in an intuitive way.


Initial Values of Purple Types
=======================================

Every *Leaf*, *Record*, *Model* and *Union* subclass has an initial (default) value.
It is set when the class is declared.

The initial value is used in elaboration for static state within a modelled system,
and when creating transient objects.

For leaves, records and unions instantiated as transient objects, the initial value is copied
into the new object on creation.

For a new leaf class, the recommended default initial value is *UnDefined*.
Unless replaced, this is automatically inherited from the *Leaf* base class.

For a new record or model class, see :ref:`Overriding Initial Values`.

For a new union class, the default initial value is the initial value of the first
of the union option classes.


Overriding Initial Values
=======================================

A *Record* or *Model* class has its own initial value.
This value may be copied, partially or entirely, from the initial values of its state attributes' classes.

The initial values of attributes with internal hierarchy (records or models) may be partially modified
in the copy.
Partial overrides use Python dictionaries and these may be hierarchical to apply partial modifications
to sub-state of a record or model state attribute.


..  code:: python

    class Example(Record):
        # attribute a has no override so takes the leaf class default, in this case UnDefined
        a: Boolean

        # attribute b initialises to True
        b: Boolean = True


    class Hierarchical_Example(Record):
        # attribute e0 is a not-overridden Example; initial value will be a:UnDefined, b:True
        e0: Example

        # attribute e1 is partially overridden; initial value will be a:UnDefined, b:False
        # note that this modification only applies to Hierarchical_Example.e1
        e1: Example = dict(b = False)

        # attribute e2 is fully overridden; initial value will be a:False, b:False
        # note that this modification only applies to Hierarchical_Example.e2
        # note that this is not possible for *Model* attributes, because creating a model instance
        #     causes elaboration of a new system
        #     however, using dict(a = False, b = False) would work for a model
        e2: Example = Example(a = False, b = False)


Initial Values and Class Inheritance
=============================================

*Record* and *Model* subclasses can be further subclassed.
Subclasses can change initial values or extend/modify initial value overrides.

Subclasses can also change the type of a state attribute.
If this happens, all initial value information from the base class is discarded.


..  code::  python

    # continues previous example

    class Derived_Example(Example):
        # this class still has an attribute b, but its initial value is different
        b = False

    class Derived_Example(Example):
        # this class still has an attribute b
        # but its type is different from the base classe so initial value is reset to UnDefined
        b: Integer[3]

    class Derived_Hierarchical_Example(Hierarchical_Example):
        # override of attribute e1 is extended; initial value will be a:False, b:False
        e1 = dict(a = False)



Special Cases of Initial Values
========================================

Initial values for instantiated *Union* types have both a type and a value, where
the type is one of the union's options.
They may be overriden fully or partially, but partial overrides only work if compatible with the
"current" initial value type.

*Array* initial values may be any Python sequence, for example a list or a generator object.
