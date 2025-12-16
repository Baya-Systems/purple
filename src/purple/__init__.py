'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

lint is not fully clean and probably cannot be, but valuable
    ruff check src --exclude __init__.py
    ruff check tst --ignore F821 --ignore F811 --ignore E722

FIXME
    clocked rules should have parameters that represent external input
        def on_clk_edge(self, index: Integer[5]):
            if trigger: etc
        so this would explode to 1 rules not 5
        require user to write a loop if they want a loop
            parameters represent external-input or specification-dont-care
            but looping over something with a guard does not work (ie guard should be same as continue)
                for p in self.ports:
                    with LocalGuards:
                        p = self.get_next()
                note that we will need to save the current state updates on entry, then add to them
                    as usual, but revert to the previous if there is a guard exception
        fix tests   DONE
        fix bomb so it has external input and re-write the doc  DONE
        add LocalGuards and test it
        fix cbusy model in BayaArch

    py3.14 breaks everything
    declaring a state type as Tuple not Tuple[XYZ] fails silently
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
    does Interface generalise to using registered-output port and initial values?
    add randomisation capability to records and leaves
        select among all-possible-values, or create on-the-fly?
        don't create all values till first call, or require a randomiser object to be created
    when you get a clocked-rule name wrong in Clock[rule_name] you get a very confusing error
    bug: can't have Tuple of Leaf
        this is temporarily hacked to work, but
        coding style is bad - test for leaf in Tuple
        no protection against transient BitVector being in-place modifiable (so non-undoable state change)
    configurable models
        how to have an array of non-identical things (eg buffers of different message types or different lengths)
        might not be an "Array", but still ought to be possible without code-in-declaration
            ie still syntactic sugar for naming of sub-components
            use of an array means not possible to use generic-Model with different parameters
        how do you specify the structure?
            configuration object, eg a transient Record but can a Record contain type references?
            what limitations on configuration make it possible to do something better than a subclass?
            eg same basic generic type but different parameters
        can a (frozen) transient Record object be a parameter to Generic?
    can I have a Tuple of Union?
    array-index variant allowing modification after elab
        only sets initial value
        question is: what are the limits on modifications?
        class X(Record):
            a: Integer[0,100] = ArrayIndexInitialiser
            b: ArrayIndex
            c: MutableArrayIndex[Integer[0,100]]

cleanup
    documentation
    move or copy all open issues/fixmes to documentation
    some fixmes are out of date and have been fixed
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
    can ArrayIndex be mutable, so just used as an initial value but then changes (eg for initialising a linked-list)?

tests todo
    model (more tests)
    inheritance (record or model) including multi-inheritance and multi-level and overrides
    enum, boolean, constant
    parameterised model and record including partial-specialisation
    shallow and deep copy of static-records to/from transient-records

support for atomic-rule specifications co-simulating with RTL as a scoreboard
    issue is that RTL micro-architecture may affect visible behaviour at boundary of device under test
    for example, if the RTL gets 2 input messages in the same clock cycle and the DUT contains an
        arbiter, then one of them will go before the other; the order may be encoded in an output if for
        example a storage buffer is assigned to each after arbitration
    there is no problem modelling this using Purple atomic-rules; 2 rules are invocable and either order
        is legal, leading to different system states
    desire is to use the Purple model as a reference for an RTL implementation, so for example
        the DUT-RTL is simulated (or analysed)
        inputs to the DUT-RTL are also applied to the Purple model
        outputs from the DUT-RTL are compared with outputs from the Purple model to see if they are legal
    legal: there exists at least one order of atomic-rule invocation which produces the RTL outputs
    so we want a Purple simulator able to search exhaustively for atomic-rule sequences that match some
        defined outputs
    probably each time there is an output it only needs to search till it finds one legal sequence,
        but remember all illegal ones so those don't need to be tested again
        and every RTL input should correspond to a (parameterised) rule invocation
        some inputs may have undefined order (eg if from different physical interfaces) and some well-defined
    how does it report "no rule sequence found"?
        up to some impossible observation there are potentially many legal sequences
        so there may be multiple legal versions of that observation
        or there may be no legal version of that observation (something else should have happened first)
        all it can say is "cannot reproduce DUT outputs x,y,z"
        but a more conventional scoreboard would say "output x is wrong, predicted xx"
        1) something came out of spec but not exact match.  give a list of
           legal options (ordered by hamming distance)
        2) something similar can out of a different interface eg address lookup error (is this the same as 1, given that nothing is predicted at that place so it will be a mismatch?)
        3) nothing came out anywhere
           have to run to deadlock for this to be a conclusion so this seems OK
    is causality an input or unimportant (ie, is it illegal behaviour for an
        output to happen before some input)?
    this is interesting and difficult to predict the complexity and performance
        build a simple example eg an arbiter

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

could add a VCD generation, but probably only useful for clocked

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
