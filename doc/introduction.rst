..
    MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>


Purple
--------------------

Purple is a simulation framework for Python(R) inspired by memory of Intel's internal "Rainbow" project.
It may be useful for digital hardware architecture exploration, validation and documentation.

Summary of Purple Concepts
=================================

* *Model*

  * a model is a Python class, typically representing some class of hardware component
  * instance objects of a model class are *static* parts of a Purple system, which means that they
    are created when the system is created and destroyed only when the system is destroyed
  * models can contain state, which can be

    * other *Models*
    * *Records*
    * *Unions*
    * *Leaves*
    * lists of *Rules*
    * *Clocks*

  * each state element within a model has a name and a type, and the model attribute can only
    be set to values matching that type

* *Record*

  * a record is a Python class, typically representing some dynamically creatable hierarchical data structure
    like a protocol packet format
  * instance objects of a record class are *transient* parts of a Purple system, which means that they
    are created within rule execution and destroyed when that execution completes (although the rule may
    copy a record into model state to preserve its content)
  * records can contain state, which can be other *Records* or *Unions* or *Leaves*
  * each state element within a record has a name and a type, and the record attribute can only
    be set to values matching that type

* *Leaf*

  * leaf classes define single state elements declared within a model or a record class
  * leaf classes available within Purple:

    * *Boolean*
    * *Enumeration* (generic)
    * *Integer* (generic: can have a finite range, or be bounded above or below)
    * *ModuloInteger* (generic)
    * *BitVector* (generic: can have a finite or infinite number of bits)
    * *Tuple* (generic: supports a single Record type for tuple elements and has unlimited length)

  * additional leaf classes can be created as required
  * leaf objects within an instantiated (elaborated) model are not usually objects of the leaf class.
    For example, the leaf class ``Integer[x]`` uses normal Python ``int`` objects as the the
    attributes of the model object that instantiates them
  * leaf objects within an instantiated (elaborated) model are immutable.
    This means that when leaf state changes value, the leaf object is replaced in the instantiating model
  * The state of an instantiated (elaborated) model is determined exclusively by the current
    values of its leaf elements

* *Union*

  * a union is a Python class used to make more complex records or leaves, used to define a state
    element within a model or record
  * a union class comprises a set of *option classes* which are all Purple record or leaf classes
  * a union state element may take a value that matches any one of its option classes

* *Port* and *Interface*

  * a port is a generic Purple *model*
  * it has a type, which can be a *Record* or *Union* or *Leaf*
  * ports form the external interfaces (along with rules) of the model in which they are declared
  * a port can be bound to another port (typically in another model) or to a handler method
    (typically in the same model)
  * when a model declares a state element that is a model, it may also declare bindings for that model's ports
  * an *interface* is a Purple *model* designed to be a base class for a group of ports commonly
    instantiated together with common parameters and bindings (for example the 5 channels of the AXI protocol)

* *Rule*

  * a rule is a method of a *Model* class which describes a way that the model's internal state can change
  * model state can only be modified within a rule execution (invocation)
  * a rule may have parameters, provided those parameters are *Records*, *Unions* or *Leaves* and provided
    that the number of possible parameter combinations is finite
  * rules are either "clocked" or "atomic".
    Clocked rules may run at the same time as each other, where atomic rules run strictly sequentially
  * the parameters of an atomic rule represent external inputs to the system
  * the parameters of a clocked rule create multiple independent and concurrent rules
  * a rule may only be invocable for a subset of the model state.
    If required, the rule embeds calculations of whether or not it is invocable.

* *Clock*

  * a clock is a state element of a *Model*
  * it has no value
  * it may be bound to a list of (clocked) rules and to other clocks for example in sub-modules
  * all rules bound to a clock are assumed to execute in parallel, seeing the same model state

* *Array*

  * an array is an ordered collection of one Purple type (*Model*, *Record*, *Union*, *Leaf*)
  * arrays are syntactic sugar for *Model* or *Record*, depending on state content and use
  * arrays of arrays are possible



Simple Atomic-Rule Example
==================================

The code below is a description of a component.
Comments within the code highlight items of interest.


..  code::  python

    # a normal Python enum
    BombState = enum.Enum('BombState', 'Ready Counting Exploded Safe')

    # the new model description is a Python class derived from the 'Model' base class
    class Bomb(Model):
        # every Bomb has a state variable called 'state' which is an enum and is initialised to 'Ready'
        state: Enumeration[BombState] = BombState.Ready

        # every Bomb has a state variable called 'count' which is an integer between 0 and 99, uninitialised
        count: Integer[100]

        # the listed methods are the ways that a Bomb can change state
        rules: [prime, countdown, cut_blue_wire, cut_red_wire]

        # 'prime' is a method with a parameter; this represents an external input
        # (in this case the user choosing a countdown duration)
        def prime(self, countdown_duration: Integer[10, 100]):
            # a guard indicates whether this rule can run or not, given the current system state
            self.guard(self.state is BombState.Ready)
            self.count = countdown_duration
            self.state = BombState.Counting

        def countdown(self):
            self.guard(self.state is BombState.Counting)
            self.count -= 1
            if self.count == 0:
                self.state = BombState.Exploded
                self.print('-----BOOM-----')

        def cut_blue_wire(self):
            self.guard(self.state is BombState.Counting)
            self.state = BombState.Safe
            self.print('phew')

        def cut_red_wire(self):
            self.guard(self.state is BombState.Counting)
            self.state = BombState.Exploded
            self.print('-----BADABOOM-----')


Simple Clocked Example
===============================

The code below is a description of a component.
Comments within the code highlight items of interest.


..  code::  python

    # a normal Python enum
    BombState = enum.Enum('BombState', 'Ready Counting Exploded Safe')

    class ClockedBomb(Model):
        # every Bomb has a state variable called 'state' which is an enum and is initialised to 'Ready'
        state: Enumeration[BombState] = BombState.Ready

        # every Bomb has a state variable called 'count' which is an integer between 0 and 99, uninitialised
        count: Integer[100]

        # there is a clock, named 'clk', which in this case drives one process rule called 'rising_edge_event'
        clk: Clock[rising_edge_event]

        def rising_edge_event(self):
            # in this example a single rule with an if statement is used instead of multiple rules with guards
            # for systems with clocked rules, external stimulus does not come from rule parameters
            # because all rules are invoked every clock cycle; in this example input is psuedo-random

            if self.state is BombState.Ready:
                # immediate change to counting state in first clock cycle
                self.count = random.randrange(20, 100)
                self.state = BombState.Counting

            elif self.state is BombState.Counting:
                # high probability that the system remains in counting state
                if random.random() < 0.975:
                    self.count -= 1
                    if self.count == 0:
                        self.state = BombState.Exploded
                        self.print('-----BOOM-----')

                # small probability that the bomb is correctly de-fused
                elif random.random() < 0.5:
                    self.state = BombState.Safe
                    self.print('phew')

                # residual probability that the bomb explodes because wrong wire cut
                else:
                    self.state = BombState.Exploded
                    self.print('-----BADABOOM-----')


Simple Example with Ports and Records
===============================================

The code below is a description of a system where multiple components are connected through
binding of their ports.
Comments within the code highlight items of interest.


..  code::  python

    # a message is an object of a class derived from the 'Record' base class
    class Message(Record):
        # a message comprises the following fields
        a_flag: Boolean
        a_number: Integer[10]

    class Producer(Model):
        # simplest form of Port can act as input or output, but always has a type
        port_out: Port[Message]
        rules: [send_message]

        # producer sends a message to its output port, using normal assignment operator
        def send_message(self, m: Message):
            self.port_out = m

    class Consumer(Model):
        last_message: Message

        # consumer input port is bound to a handler function, which gets called when
        # a new value arrives
        port_in: Port[Message] >> port_in_handler

        def port_in_handler(self, m):
            # print something and store the message in a local state variable
            if m.a_flag:
                self.print('received', m.a_number)
            self.last_message = m

    # top contains one producer and one consumer
    # the consumer's input port is bound to the producer's output port
    class Top(cli.Test.Top):
        p: Producer
        c: Consumer[_.port_in << p.port_out]
