..
    MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>


Purple in Verification
-----------------------------------

Atomic-Rule Specification
=====================================

The purple sub-module ``verif`` provides some base classes which can help to use an atomic-rule
specification model of a component as a verification reference (scoreboard) for
an implementation.

There is an example in the ``tst_verif`` directory.
It comprises:

* a specification model of a simple re-order buffer component, defined in the
  class ``ReOrderBufferSpec`` in ``rob_spec_test.py``.
  This is an atomic-rule purple model
* an example implementation of a component matching the specification, in ``rob_implementation_test.py``,
  along with a testbench for verifying this component's correctness.
  Note that this testbench does not use the specification purple code.
  The implementation is written as a purple clocked component.
  This is simply so that it can run wholly within a pure-python environment; normally an implementation
  would be coded in synthesisable Verilog and would require a Verilog simulator with
  embedded python capability
* a testbench, in ``rob_checker_test.py``, which extends the implementation
  testbench to include checking against the specification

The objective of the verif sub-module is to enable checking within a simulation of a Verilog component.
It should also be possible to do a formal comparison between a Verilog implementation and
a purple specification, but this would be a different topic.
On that subject however a couple of the axioms of the purple project should be remembered:

* specification models are not expected to be complete; when creating a specification model
  only a subset of the component functionality may be included
* specification models are often not clocked and without any concept of time, and almost
  never cycle-accurate

The verif sub-module is used as follows.
The initial premise is that both an implementation and a specification exist, for the same component.

The specification:

* is a purple atomic-rule model
* has inputs which are "pull" ports and outputs which are "push" ports.
  That is, rules within the component cause the component to attempt to fetch new inputs from somewhere
  or attempt to send outputs to somewhere

The implementation also has a testbench, which provides stimulus inputs to the implementation
model and consumes its outputs.

A component-specific purple testbench must be created for the specification model.
This testbench can be derived from ``verif.StimulusIOTestbenchBase``.
It should instantiate a ``verif.StimulusInput`` for every specification input port and a
``verif.StimulusOutput`` for every specification output port.
It should also instantiate a component specification model and bind the
``port_for_spec_input`` or ``port_for_spec_output`` attributes of the input/output
objects to its ports.
It should also implement methods ``stimulus_inputs(self)`` and ``stimulus_outputs(self)`` which
return lists or tuples of the input/output objects.

Input and output stimulus objects are generic and need to be given the correct type on instantiation.

The stimulus-input objects do the following:

* store timestamped copies of all inputs that the implementation model has received during
  the simulation
* deliver these values in order to the specification model when it so requests
* refuse to deliver values timestamped after the earliest unmatched output, because
  this wastes simulation time testing for a non-causal implementation

The stimulus-output objects do the following:

* store timestamped copies of all outputs that the implementation model has provided during
  the simulation
* when the specification model provides an output, checks if it matches the next
  output expected for that port

The implementation testbench (or simulator) should be extended so that:

* it can create and access a specification testbench as described above
* when it runs, advancing simulated time, it captures all implementation inputs and
  outputs and copies them to the input/output objects in the specification testbench
* every so often (or at the end of simulation) it calls the ``checksearch()`` method
  of the specification testbench.
  This attempts to find a sequence of atomic rules which replicates the implementation
  outputs using the implementation inputs

If check-search succeeds, it is usually pretty fast.

If there is a bug or a difference in behaviour between specification and implementation,
then check-search needs to explore all possible sequences of specification rules
to confirm that all sequences fail to produce the right output.
This can take some time, especially if the simulation is long.
Two speed-enhancing features are included:

* see above, inputs are not taken till all previous outputs have been matched
* the state of the specification model is hashed and whenever it is proved that from
  a state X there is no path to a matching output, hash(X) is added to a set of
  impossible states.
  Whenever a rule invocation takes the specification model to a state Y where hash(Y)
  is in the set of impossible states, the search is abandoned for Y.
  This optimisation assumes that hash collisions, ie hash(X) and hash(Y) are the same
  but X and Y are different, are rare

If check-search fails to find a match, the testbench method ``report_after_fail()`` may
be called.
This will print out the last matched output at every port, and the first unmatched output.
Then it will show the input stimulus around the time of the first unmatched output.
Note that this is not a depiction of one particular rule sequence but the furthest that
it was possible to go at each port across all tested rule sequences.

From the example we can see that flow control, in this case a valid/ready handshake, is not
part of the specification model and does not need to be part of the IO for the specification model.
Inputs and outputs in the implementation testbench are captured when valid and ready are both True.
All the signals qualified by a valid/ready pair are captured together and converted to a
single Record object.
When the valid and ready signals change state is under the control of the verification IP
in the implementation testbench, as is the content of the other IO signals.
This means the implementation testbench runs like a normal testbench with either random
or directed stimulus; the specification model only acts as a functional scoreboard reporting
on whether a set of inputs and outputs can be specification-compliant or not.


Clocked Specification
=====================================

No support included at the moment.

What might be meant here:

* specification takes the form of a Purple clocked model
* model is incomplete; there are aspects of the implementation that are don't-care in the model
* so the model is some kind of pipeline specification; perhaps without actual data processing functionality.
  For example a cache controller:

  * Read and Write transactions come into the controller
  * they get looked up in its tag memories to find out if they "hit" or "miss" the cache
  * transactions that hit are completed within the cache itself, but transactions that
    miss are sent onwards to system memory
  * the pipeline model doesn't care about cache functionality so instead of looking up
    in the tag memories it simulates the time that would take then gets the hit/miss decision
    as an external input (a parameter to a clocked rule)

Such a model should be useable as a reference for a full implementation in a similar way to
an atomic-rule model as described above.
The same inputs should be fed into the model as were fed into the implementation, at every clock cycle.
The same outputs should be expected from the model as from the implementation, at every clock cycle.
The simulation of the model can be varied by selection of clocked rules or rule parameters, until
a sequence is found where it matches the implementation.
