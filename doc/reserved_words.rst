..
    MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>


Purple Reserved Words
--------------------------------

List of identifiers used for specific purposes by Purple, therefore not available as
names of state elements or rule methods or handler methods, etc..

* ``_`` a single underscore

  Underscores are used to refer to the state element currently being declared, and
  can't be used within a *Record* or *Model* class declaration for any other purpose

* ``_dp_*``

  Methods and attributes starting underscore-dp-underscore are treated in a special
  way, bypassing normal Purple set/get mechanisms

* for *Model* subclasses

  * ``rules``
  * ``end_of_elaboration`` (not yet implemented)
  * ``name``

    Every instantiated static *Record* or *Model* object has a name attribute

  * ``update``
  * ``find_rule``
  * ``find_clock``
  * ``guard``
  * ``print``
  * ``guards_limited_to_code_block``
  * ``update_dp_initial_value_from_base``

* for *Record* subclasses

  * ``name``

    Every instantiated static *Record* or *Model* object has a name attribute

  * ``update``
  * ``copy``
  * ``deep_copy``
  * ``freeze``
  * ``melt``
  * ``guard``
  * ``print``
  * ``guards_limited_to_code_block``
  * ``update_dp_initial_value_from_base``
  * ``make_class``

* all reserved words from normal Python
