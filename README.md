<!--- MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com> -->

# Purple

A simulation framework for Python(R) inspired by memory of Intel's internal "Rainbow" project

Purple may be useful for digital hardware architecture exploration, validation and documentation.
It has the following goals:

* declarative creation of hierarchies of interacting components

  * clearly visible system state
  * well-defined inter-component interfaces (ports)

* description of component behaviour with more than one option for representing concurrent
  changes to internal state

  * atomic "rules"
  * "clocked" processes
  * behaviour triggered by external stimulus

* clearly visible component behaviour allowing "model-is-specification"

* ability to estimate functional or state coverage

  * achieved during a simulation
  * (future) through static analysis of state transition possibilities

* strong type checking

  * when components are declared
  * dynamic during simulation execution
  * (future) compatible with static code analysis type checking frameworks

* ability to undo/replay simulation steps
* (future) ability to save/restore simulation state
* (future) ability to translate a subset of Purple into some language supported by formal analysis tools
* (future) ability to co-simulate a Purple system with Verilog using DPI
* pure-Python implementation and all user code is standard Python

## Approach

Purple uses the type-hinting syntax of Python to declare component state variables, port bindings and
other things.

This leads to a concise and readable model, but is contrary to Python's recommendations around use
of type hinting.
There are other widely-accepted Python projects which similarly use type hinting for functional reasons,
for example *attrs*, but probably less aggressively than Purple.

## Status

Implementation is complete enough for many projects.
Tests exist for the vast majority of implemented features.

The whole Purple project is threatened by the change in type hinting support scheduled for Python 3.14.
This change will certainly break the current implementation of Purple.
It may or may not be possible to upgrade Purple to be compatible with Python 3.14 but it is unlikely
that the use model (syntax) will be preserved exactly, or that Purple will be able to be compatible with
both pre 3.14 and post 3.14 versions of Python.

Main weaknesses of the current version are:

* lack of clarity of error messages (Python exceptions) means familiarity with implementation
  too often required when something goes wrong
* there are a few gaps in testing
* simulators are rudimentary and not yet interactive
* user documentation, although the tests may provide insight into how to use features
* contributor documentation

## Installation

Purple is pure-python and has no dependencies.

It can be used simply by cloning the project and adding the ``src`` directory to the
python module search path (``PYTHONPATH``).

There is a ``pyproject.toml`` file which supports adding purple as a site/user module for the
current python installation.
This means that no search path modification is needed.
After cloning, run ``pip install $PURPLE_ROOT_DIRECTORY``.
