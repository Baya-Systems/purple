'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

done
    metaclasses
    hierarchy / model
    record
    union
    port
    parameterised classes
    state (enum, integer, modulo, boolean, constant)
    rule
    array
    tuple
    bit-vector
    clock
    interface
    simulator

lint is not fully clean and probably cannot be, but valuable
    ruff check src --exclude __init__.py
    ruff check tst --ignore F821 --ignore F811 --ignore E722

FIXME
    declaring a state type as Tuple not Tuple[XYZ] fails silently
    py3.14 breaks everything
    start rules
        class X(Model):
            b: SomeType
            end_of_elaboration: make_b
            def make_b(self): self.b = blah
    invariants
    coverage definition methods
    array with enum keys
    save/restore
    ability to suppress a rule in subclass
    cosimulation with Verilog-DPI
    clocked rules could have parameters that represent external input
        def on_clk_edge(self, index: Integer[5], trigger: ExternalInput[Boolean]):
            if trigger: etc
        so this would explode to 5 rules not 10

cleanup
    documentation
    am I allowing partially-undef records to be compared for equality?  is it OK?
    search for all " if _dp_class_is_something " and try to replace with classmethods
        then define clearly what the expected classmethod behaviour is
    improve all Exceptions to trap specific things eg CastToLeafFailure
    can raise exceptions higher up in the stack, to hide your internals...
        eg in rule.invoke or invocation.__exit__, do something like the following
        to hide PurpleException.assert and other layers of purple mess
        "raise Exception("foo occurred").with_traceback(tracebackobj)"
        If the traceback of the active exception is modified in an except clause, a subsequent raise statement re-raises the exception with the modified traceback.  also true for __exit__? do we even re-raise or just print
        and offer to post-mortem or re-run?
    names of generated classes
    test that ambiguous references in declaration are actually used rather than bugs (eg "stophere") - or maybe remove ambiguous references completely (may be needed for rules?)
    good error messages, eg if combined initial values don't match any union option
    type checking on class declaration
        rules are type-annotated with (finite?) Record and Leaf types
        ports bind to handlers with the right Record/Leaf type
        ports bind to ports with the right Record/Leaf type
        ports bind in the right direction and fan in/out is controlled
    replace star-import with named set of things
    support copying records from superclasses and subclasses?
    force port payload type to be a record or a leaf

tests todo
    model (more tests)
    inheritance (record or model) including multi-inheritance and multi-level and overrides
    enum, boolean, constant
    parameterised model and record including partial-specialisation
    shallow and deep copy of static-records to/from transient-records

need to decide on immediate-visibility in clocked rules
    at the moment I am in favour of immediate visibility, because of a bad experience with
    passing a static-record by reference through a port
    also seems very strange to allow multiple in-place updates if the code cannot see the
    previous updates
    note that updates to the same leaf from different clocked rules at the same cycle
    should never be allowed, because determinism in the general case is really hard
        (eg one rule does x /= 2 and another rule does x += 1)
    this simplifies bitvector

could this go full-bs?
    that is run a clocked simulation from a set of atomic rules
    attempt to invoke all rules in every clock cycle, from same start state
        assume any pair of rules that overlap cannot be run in the same clock cycle
        needs some arbitration to select between collisions
        does this require knowledge of which rules are reading which parts of system state?
        is it limited to rules without parameters, if parameters represent external stimulus?
    even further
        allow one rule to forward state to another, so the 2 can run sequentially
            in the same cycle
        allow a rule to need multiple clock cycles to complete
            does it read per cycle but hold all writes till the end?
            so that it can be abandoned if atomicity was violated during run
            can you pipeline, so multiple instances of the same rule
                read all at the start?

are greek characters just a distraction?
    πψτηον
'''

from .__about__ import __version__

from .common import *
from .record import *
from .model import *
from .static_record import *
from .leaf import *
from .port import *
from .union import *
from .array import *
from .state import *
from .tuple import *
from .bitvector import *
from .clock import *
from .parameterise import *
from .interface import *
from .simulator import *
