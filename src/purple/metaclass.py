'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

metaclass for Purple models

FIXME
    initial value as a dict comprehension

    can I derive a Model from a Record?
    for sure not the other way round
    might work
        class X(Record):
            a: int

        class Y(Model, X):
            b: bool
            rules: [blah]
'''

import inspect
import annotationlib
import sys

from . import common


class PurpleComponentMetaClass(type):
    def __or__(cls, other_cls):
        'create a Union of a purple state classes and another state class'
        from . import union
        if other_cls is None:
            from . import state
            return union.Union | state.Constant[None] | cls
        else:
            return union.Union | cls | other_cls

    def __rmul__(cls, array_length):
        from . import array
        return array.Array[array_length, cls]


class PurpleLeafMetaClass(PurpleComponentMetaClass):
    def __call__(cls, value_to_cast = common.UnDefined):
        '''cannot create Leaf objects, the Leaf classes cast, usually to some simple immutable object'''
        return cls._dp_check_and_cast_including_undef(None, '', value_to_cast, False)


class UnionMetaClass(PurpleComponentMetaClass):
    def __or__(cls, other_cls):
        'create a Union of a union and another union or purple state class'
        return cls.make_class(other_cls)

    def __eq__(cls, other_cls):
        return isinstance(other_cls, type(cls)) and \
            cls._dp_union_class_options == other_cls._dp_union_class_options

    def __hash__(cls):
        return hash(cls._dp_union_class_options)

    def __call__(cls, *args, **kwargs):
        'used to create transient objects which will be from one of the option classes'
        for option_cls in cls._dp_union_ordered_options:
            try:
                return option_cls(*args, **kwargs)
            except Exception as ex:
                # FIXME TOO LENIENT
                continue
        raise ValueError


class PurpleTypeProxy:
    ''' all sub-component (and other annotations) are added to the class being
    declared as class variables, objects of this type

    for use in lazily-evaluated expressions eg bindings and rule lists

    basically is just a hierarchical name
    the purple-type (tree) corresponding to the name is stored in _dp_state_types

    name elements can be strings, or for arrays ints or slices
    Model._dp_add_bindings_from_annotations()
        is responsible for converting the ints and slices into correctly-named single-bindings
    '''
    def __init__(self, name, hierarchical_name):
        if name == '':
            self.name = tuple(hierarchical_name)
        else:
            self.name = (*hierarchical_name, name)

    def __getattr__(self, attr_name):
        return PurpleTypeProxy(attr_name, self.name)

    def __getitem__(self, index):
        'for binding eg ports within arrays'
        if isinstance(index, (int, slice)):
            return PurpleTypeProxy(index, self.name)
        else:
            raise IndexError

    def __lshift__(self, bind_target):
        return Binding(self, bind_target, False)

    def __rshift__(self, bind_target):
        return Binding(self, bind_target, True)


class Binding:
    ''' bindings should only be

    RHS: method (function object ref for a handler)
    LHS: port-class (when doing immediate binding of a handler)
    type-proxy on LHS or RHS

    Port-to-port binding
        put in a class-getitem, or standalone bind-declaration
            x: myModel[port_in_x << other.port_out_other]
            y: myModel
            more declarations may be between
            bind_name_needed_but_ignored: [
                y.port_in_x << other2.port_out_other,
            ]

    Port-to-handler binding
        could be for input port to call when a value arrives (push)
        could be for output port to call whan a value requested (pull)
        done by overriding shift on the class or on a reference to a prior annotation
            x: myPort >> handler_method_name
            y: myPort
            y >> other_handler_name
    '''
    def __init__(self, lhs, rhs, left2right, add_to_mcs = True):
        self.lhs = lhs # always a proxy object
        self.rhs = rhs # may be a proxy object or a function object (local method)
        self.left2right = left2right

        if add_to_mcs:
            if not MetaClassState.peek().enable_binding_capture:
                raise NameError('binding capture not enabled')
            MetaClassState.add_binding(self)

    def resolve(self, discovered_forename, purple_type):
        # need to convert to names for which we need to replace a type/function with a proxy
        if self.lhs is purple_type:
            self.lhs = PurpleTypeProxy(discovered_forename, ())
        if inspect.isfunction(self.rhs):
            self.rhs = PurpleTypeProxy(self.rhs.__name__, ())

    def __str__(self):
        lhs = '.'.join(str(n) for n in self.lhs.name)
        rhs = '.'.join([self.rhs.__name__] if inspect.isfunction(self.rhs) else (str(n) for n in self.rhs.name))
        return f'{lhs.rjust(30)} {">>" if self.left2right else "<<"} {rhs}'


class ATSMetaClassBase(type):
    pass


def AddToState(**cls_variables):
    ''' method returning a base class for adding state elements programmatically,

    that is when the state name is not a literal
    first example is in array.py, where state elements are added in a loop

    in the declaration of the Purple Model or Record, declare an inner (nested) class
    which is a subclass of AddToState()
    pass whatever class variables you need to AddToState
    in the inner class, declare state elements and bindings, etc as normal and
    they will be added to the outer class with adapted names
    '''
    class ATSMetaClass(ATSMetaClassBase):
        @classmethod
        def __prepare__(metacls, name, bases, cls_namespace = cls_variables.copy()):
            return cls_namespace

    def default_nameconv(cls, statename, clsv = '_'.join(str(v) for v in cls_variables.values())):
        ''' this becomes the classmethod(adapt_name) in the add-to-state class

        takes a state name in the add-to-state class, the key in the type annotation
            and returns the name of the state element to be added in the outer class
        it can be overridden in the derived class as required

        default first looks for a class variable called <statename>_name
        and if it doesn't find it, applies all the other class variables
        '''
        if name := getattr(cls, f'{statename}_name', None):
            return name
        else:
            return f'{statename}_{clsv}'

    def init_subclass(cls, **kwargs):
        MetaClassState.peek().addtostate_classes.append(cls)

    cls_variables['adapt_name'] = classmethod(default_nameconv)
    cls_variables['__init_subclass__'] = classmethod(init_subclass)
    return ATSMetaClass('PurpleAddToState', tuple(), cls_variables)


# cannot use class variable, because they can be trashed by get_annotations()
MetaClassStateStack = []

class MetaClassState:
    '''
    addtostate_classes is used by AddToState to record inner class declarations
    raw_bindings is used by Binding expressions to record themselves during __new__()
    and new_bindings because we need to replace "_" with the actual annotation name

    need a stack because of nested class declarations and also because of
    generic class creation during annotation evaluation
    '''
    # FIXME we may be adding the same binding multiple times as
    # we re-evaluate annotations
    @classmethod
    def push(cls):
        self = cls()
        self.addtostate_classes = []
        self.raw_bindings = []
        self.new_bindings = []
        self.enable_binding_capture = False
        MetaClassStateStack.append(self)

    @classmethod
    def peek(cls):
        return MetaClassStateStack[-1]

    def pop(self):
        assert MetaClassStateStack.pop(-1) is self

    @classmethod
    def get_annotations(cls, target, format):
        return annotationlib.get_annotations(target, format = format)

    # change any binding LHS which is a purple-class into a proxy with the annotation-name
    @classmethod
    def after_annotations(cls, element_name, element_type):
        state = cls.peek()
        if state.new_bindings:
            for b in state.new_bindings:
                b.resolve(element_name, element_type)
            state.raw_bindings.extend(state.new_bindings)
            state.new_bindings = []

    @classmethod
    def add_binding(cls, binding):
        state = cls.peek()
        if state.enable_binding_capture:
            MetaClassState.peek().new_bindings.append(binding)
        else:
            # force creation of a ForwardRef that we can re-evaluate with capture enabled
            # thus allowing replacement of "_" and [Port] classes in after-annotations
            raise NameError('binding capture not enabled')


def eval_string_annotation(ann_str: str, owner):
    ''' evaluate a STRING-format annotation with exactly the same context that FORWARDREF would use

    (Claude generated, only works for classes)
    needed because FORWARDREF ignores class-getitem or metaclass-getitem
    which may be a bug in CPython which will be fixed in a future release

        https://github.com/python/cpython/issues/138425
        if we use Format.VALUE or Format.FORWARDREF, it just assumes MyClass[a << b]
        and returns MyClass; a<<b is not evaluated
    '''
    assert isinstance(owner, (PurpleHierarchicalMetaClass, ATSMetaClassBase))
    globs = vars(sys.modules[owner.__module__])

    # Recover enclosing-function locals captured as closure cells in __annotate__
    locs = dict(vars(owner))

    annotate = getattr(owner, '__annotate__', None)
    if annotate is not None:
        freevars = annotate.__code__.co_freevars
        cells = annotate.__closure__ or ()
        for name, cell in zip(freevars, cells):
            try:
                locs[name] = cell.cell_contents
            except ValueError:
                pass  # cell is empty (variable not yet assigned)

    type_params = getattr(owner, '__type_params__', ())

    ref = annotationlib.ForwardRef(ann_str, owner = owner)
    return ref.evaluate(
        format = annotationlib.Format.FORWARDREF, globals = globs, locals = locs, type_params = type_params
    )


class PurpleHierarchicalMetaClass(PurpleComponentMetaClass):
    '''
    metaclass abuses the Python type annotation syntax to support declaration of the following
    - model/record internal state hierarchy
    - internal state initial values
    - rules for internal state modification
    - binding of ports and port-handlers

    metaclass-state-stack allows nested class declaration, provides a place for bindings and
        add-to-class declarations to store themselves

    metaclass supports deriving subclasses and overriding declarations from the base class(es)
    '''

    @classmethod
    def __prepare__(metacls, name, bases):
        MetaClassState.push()
        return super().__prepare__(name, bases)

    def __new__(metacls, name, bases, classdict):
        mc_state = MetaClassState.peek()
        cls = type.__new__(metacls, name, bases, classdict)
        unique_obj = common.UniqueObject

        # capture raw initial values, which are evaluated on the fly by python,
        # and replace with Proxy objects for binding evaluation
        if '_' in vars(cls):
            delattr(cls, '_')
        cls_annotations = MetaClassState.get_annotations(cls, annotationlib.Format.STRING)
        raw_initial_value = dict()
        for n in cls_annotations:
            riv = getattr(cls, n, unique_obj)
            if isinstance(riv, PurpleTypeProxy):
                riv = unique_obj
            raw_initial_value[n] = riv
            setattr(cls, n, PurpleTypeProxy(n, ()))

        # and for addtostate nested classes
        for ats_class in mc_state.addtostate_classes:
            if hasattr(ats_class, '_'):
                delattr(ats_class, '_')
            ats_annotations = MetaClassState.get_annotations(ats_class, annotationlib.Format.STRING)

            for n in ats_annotations:
                name_in_cls = ats_class.adapt_name(n)
                riv = getattr(ats_class, n, unique_obj)
                if isinstance(riv, PurpleTypeProxy):
                    riv = unique_obj
                raw_initial_value[name_in_cls] = riv

            # everything from the class being declared is available in the ATS class
            setattr(ats_class, name, cls)

            # but local things override them
            for n in ats_annotations:
                cls_proxy = PurpleTypeProxy(name_in_cls, ())
                setattr(cls, name_in_cls, cls_proxy)
                setattr(ats_class, n, cls_proxy)

        # FIXME
        # problem here? want to preserve non-Purple type annotations
        # and non-Purple class variables
        # so if any annotation resolves to something that isn't a Purple Model then don't replace it

        # state elements in base classes already have proxies which are visible to lazy evaluation
        # but the new cls may override an initial value by just setting a class variable
        # without a type annotation, so check for that
        for base in bases:
            # order of bases does not matter; we just need all the hierarchical state names
            if isinstance(base, metacls):
                for n in base._dp_state_types:
                    if n not in raw_initial_value:
                        iv = getattr(cls, n, unique_obj)
                        if (iv is not unique_obj) and (not isinstance(iv, PurpleTypeProxy)):
                            raw_initial_value[n] = iv

        # now evaluate the class annotations properly
        def re_eval(annot_name, annot_str, annot_class):
            annot_class._ = PurpleTypeProxy(annot_name, ())
            annot = eval_string_annotation(annot_str, annot_class)

            if isinstance(annot, annotationlib.ForwardRef):
                rv = annot.evaluate(format = annotationlib.Format.STRING)
                assert '__annotationlib_name_' not in rv
                assert False, f'{annot_name}: {rv}'
            elif isinstance(annot, list):
                # special case; forward-ref will return a list (eg for "rules") which can contain
                #   - evaluated things like methods
                #   - proxy objects eg names of methods in subcomponent
                #   - forward-ref eg name of a method that will be declared in a subclass
                rv = []
                for a in annot:
                    if isinstance(a, annotationlib.ForwardRef):
                        rvs = a.evaluate(format = annotationlib.Format.STRING)
                        rv.append(rvs)
                        assert '__annotationlib_name_' not in rvs
                    else:
                        rv.append(a)
            else:
                # functions and other things that got evaluated first time
                rv = annot

            MetaClassState.after_annotations(annot_name, rv)
            return rv

        mc_state.enable_binding_capture = True
        raw_annotations = {n:re_eval(n, a, cls) for n,a in cls_annotations.items()}

        # and evaluate within addtostate nested classes
        for ats_class in mc_state.addtostate_classes:
            mc_state.enable_binding_capture = False
            if '_' in vars(ats_class):
                delattr(ats_class, '_')
            ats_annotations = MetaClassState.get_annotations(ats_class, annotationlib.Format.STRING)
            mc_state.enable_binding_capture = True
            raw_annotations |= {
                ats_class.adapt_name(n):re_eval(n, a, ats_class) for n,a in ats_annotations.items()
            }

        cls._dp_initial_value = dict()
        cls._dp_state_types = dict()
        cls._dp_rule_names = set()
        cls._dp_bindings = list()
        cls._dp_clock_declarations = dict()

        # get state, etc from all base classes in reverse order so that
        # more recent overrides older in the base class list
        for base in reversed(bases):
            if isinstance(base, metacls):
                cls._dp_add_state_from_base(base)
                cls._dp_add_rules_from_base(base, PurpleTypeProxy)
                cls._dp_add_bindings_from_base(base)
                cls._dp_add_clocks_from_base(base)

        # get new state from this class's annotation hints
        cls._dp_add_state_from_annotations(raw_annotations)
        cls._dp_add_rules_from_annotations(PurpleTypeProxy, raw_annotations)
        cls._dp_add_bindings_from_annotations(mc_state.raw_bindings)
        cls._dp_add_clocks_from_annotations(raw_annotations)

        # now do the initial-values, later so that type changes are visible to bases
        for base in reversed(bases):
            if isinstance(base, metacls):
                cls.update_dp_initial_value_from_base(base, raw_initial_value)
        cls.update_dp_initial_value_from_base(cls, raw_initial_value)

        # hook for classes to do things when instantiated (eg port type checking)
        for state_element_name,state_element_type in cls._dp_state_types.items():
            state_element_type._dp_on_instantiation(cls, state_element_name)

        mc_state.pop()
        return cls

    def __getitem__(cls, index):
        '''used to add extra info on declaration, eg a set of port bindings

        and allows the bindings to be abbreviated
        (declaration name can be replaced by "_")

        records any generator expressions so that they can be iterated out as soon as
        the annotation is known
        '''
        return cls

    def __rshift__(cls, handler_name):
        'used to bind a port to a local port-handler function'
        Binding(cls, handler_name, True)
        return cls

    def __lshift__(cls, handler_name):
        'used to bind a port to a local port-handler function'
        Binding(cls, handler_name, False)
        return cls
