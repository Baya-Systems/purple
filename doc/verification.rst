..
    MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>


Purple in Verification
-----------------------------------

Atomic-Rule Specification
=====================================

Add text here


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
