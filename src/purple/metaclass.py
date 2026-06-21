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

from . import common


class PurpleComponentMetaClass(type):
    generic_array = None

    def __or__(cls, other_cls):
        'create a Union of a purple state classes and another state class'
        return UnionMetaClass.union_base_class | cls | other_cls

    def __rmul__(cls, array_length):
        return PurpleComponentMetaClass.generic_array[array_length, cls]


class PurpleLeafMetaClass(PurpleComponentMetaClass):
    def __call__(cls, value_to_cast = common.UnDefined):
        '''cannot create Leaf objects, the Leaf classes cast, usually to some simple immutable object'''
        return cls._dp_check_and_cast_including_undef(None, '', value_to_cast, False)


class UnionMetaClass(PurpleComponentMetaClass):
    union_base_class = None

    def __new__(metacls, name, bases, classdict):
        cls = type.__new__(metacls, name, bases, classdict)
        if metacls.union_base_class is None:
            # this is done to break circular import
            assert name == 'Union'
            metacls.union_base_class = cls
        return cls

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
    ''' returned when a class declaration includes a reference to a declared sub-component (annotation)

    for use in lazily-evaluated expressions eg bindings and rule lists

    if we refer to a previously-declared sub-component, we need to be able to get a
    similar reference for its internal sub-state
    '''
    def __init__(self, name, purple_type, hierarchical_name):
        self.name = (*hierarchical_name, name)
        self.purple_type = purple_type

    def resolve(self, discovered_forename, top_purple_type):
        if self.name[0] == '_':
            self.name = discovered_forename, *self.name[1:]
            purple_type = top_purple_type
            for sub_name in self.name[1:]:
                purple_type = purple_type._dp_state_types[sub_name]
            self.purple_type = purple_type

    def __getattr__(self, attr_name):
        if self.purple_type is common.UniqueObject:
            purple_type = common.UniqueObject
        else:
            purple_type = self.purple_type._dp_state_types.get(attr_name)
        return PurpleTypeProxy(attr_name, purple_type, self.name)

    def __getitem__(self, index):
        'for binding eg ports within arrays'
        if isinstance(index, slice):
            return [self[i] for i in self.purple_type._dp_array_slice_range(index)]
        elif self.purple_type is common.UniqueObject:
            return getattr(self, str(index))
        elif index >= 0 and index < self.purple_type._dp_array_length:
            return getattr(self, self.purple_type._dp_array_2attrname(index))
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
            [
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
    def __init__(self, lhs, rhs, left2right):
        self.lhs = lhs # always a proxy object
        self.rhs = rhs # may be a proxy object or a function object (local method)
        self.left2right = left2right
        PurpleHierarchicalMetaClass.add_binding(self)

    def resolve(self, discovered_forename, purple_type):
        if self.lhs is purple_type:
            self.lhs = PurpleTypeProxy(discovered_forename, purple_type, ())

    def convert_to_names(self):
        if inspect.isfunction(self.rhs):
            self.rhs = PurpleTypeProxy(self.rhs.__name__, None, ())
        assert hasattr(self.lhs, 'name'), self.lhs
        assert self.lhs.name[0] != '_' and self.rhs.name[0] != '_'
        return self

    def __str__(self):
        lhs = '.'.join(self.lhs.name)
        rhs = '.'.join([self.rhs.__name__] if inspect.isfunction(self.rhs) else self.rhs.name)
        return f'{lhs.rjust(30)} {">>" if self.left2right else "<<"} {rhs}'


def AddToState(**cls_variables):
    class ATSMetaClass(type):
        @classmethod
        def __prepare__(metacls, name, bases, cls = cls_variables.copy()):
            ns = cls
            return ns

    def default_nameconv(cls, statename, clsv = '_'.join(str(v) for v in cls_variables.values())):
        return f'{statename}_{clsv}'

    def init_subclass(cls, **kwargs):
        print('init-subclass', cls)
        current_dp_cls = PurpleHierarchicalMeta.namespace_stack[-1]
        current_dp_cls['__dp_addtostate_classes'].append(cls)

    cls_variables['purple_statename_conversion'] = classmethod(default_nameconv)
    cls_variables['__init_subclass__'] = classmethod(init_subclass)
    return ATSMetaClass('PurpleAddToState', tuple(), cls_variables)


class PurpleHierarchicalMetaClass(PurpleComponentMetaClass):
    '''
    metaclass abuses the Python type annotation syntax to support declaration of the following
    - model/record internal state hierarchy
    - internal state initial values
    - rules for internal state modification
    - binding of ports and port-handlers

    namespace-stack allows nested class declaration, provides a place for bindings and
        add-to-class declarations to store themselves

    metaclass supports deriving subclasses and overriding declarations from the base class(es)
    '''
    namespace_stack = []
    evaluating = None

    @classmethod
    def __prepare__(metacls, name, bases):
        ns = super().__prepare__(name, bases)
        ns['__dp_addtostate_classes'] = []
        metacls.namespace_stack.append(ns)
        return ns

    def __new__(metacls, name, bases, classdict):
        assert metacls.namespace_stack.pop() is classdict
        cls = type.__new__(metacls, name, bases, classdict)
        metacls.evaluating = cls
        unique_obj = common.UniqueObject

        # FIXME some of these are only needed during evaluation (raw)
        # so we can do a better job of metacls.evaluating
        cls._dp_raw_annotations = dict()
        cls._dp_raw_bindings = list()
        cls._dp_raw_initial_value = dict()
        cls._dp_initial_value = dict()
        cls._dp_state_types = dict()
        cls._dp_rule_names = set()
        cls._dp_bindings = list()
        cls._dp_clock_declarations = dict()

        # get all state element declarations
        fwdref = annotationlib.Format.FORWARDREF
        strref = annotationlib.Format.STRING
        annotations = annotationlib.get_annotations(cls, format = fwdref)

        # capture raw initial values, which are evaluated on the fly by python,
        # and replace with Proxy objects for binding evaluation
        riv = cls._dp_raw_initial_value
        for n,a in annotations.items():
            riv[n] = getattr(cls, n, unique_obj)
            setattr(cls, n, PurpleTypeProxy(n, unique_obj, ()))

        # FIXME
        # problem here?  want to preserve non-Purple type annotations
        # and non-Purple class variables
        # so if any annotation resolves to something that isn't a Purple Model then don't replace it

        # FIXME
        # also need to replace all state from base classes
        # and from addtostate nested classes

        # now evaluate the class annotations
        for n,a in annotations.items():
            # set underscore to the name of the state element
            setattr(cls, '_', getattr(cls, n))
            # evaluate will also create any bindings that have been declared
            if isinstance(a, annotationlib.ForwardRef):
                cls._dp_raw_annotations[n] = a.evaluate()
            elif isinstance(a, list):
                # special case; forward-ref will return a list
                x = []
                for aa in a:
                    if isinstance(aa, annotationlib.ForwardRef):
                        try:
                            x.append(aa.evaluate())
                        except:
                            x.append(aa.evaluate(format = strref))
                    else:
                        x.append(aa)
                cls._dp_raw_annotations[n] = x
            else:
                # functions and other things that got evaluated first time
                cls._dp_raw_annotations[n] = a

        # get state, etc from all base classes in reverse order so that
        # more recent overrides older in the base class list
        for base in reversed(bases):
            if isinstance(base, metacls):
                cls._dp_add_state_from_base(base)
                cls._dp_add_rules_from_base(base, PurpleTypeProxy)
                cls._dp_add_bindings_from_base(base)
                cls._dp_add_clocks_from_base(base)

        # get new state from this class's annotation hints
        cls._dp_add_state_from_annotations()
        cls._dp_add_rules_from_annotations(PurpleTypeProxy)
        cls._dp_add_bindings_from_annotations(cls._dp_raw_bindings)
        cls._dp_add_clocks_from_annotations()

        # now do the initial-values, later so that type changes are visible to bases
        for base in reversed(bases):
            if isinstance(base, metacls):
                cls.update_dp_initial_value_from_base(base)
        cls.update_dp_initial_value_from_base(cls)

        # hook for classes to do things when instantiated (eg port type checking)
        for state_element_name,state_element_type in cls._dp_state_types.items():
            state_element_type._dp_on_instantiation(cls, state_element_name)

        metacls.evaluating = None
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

    @classmethod
    def add_binding(metacls, binding):
        metacls.evaluating._dp_raw_bindings.append(binding)

    @classmethod
    def resolve_bindings(metacls, forename, purple_type):
        '''called when an annotation is added and its name becomes known
        '''
        # FIXME IS THIS NO LONGER A CLASSMETHOD

        # fix any direct-to-port bindings
        for b in metacls.evaluating._dp_raw_bindings:
            b.resolve(forename, purple_type)

        # explode all binding-generators
        # FIXME NOT SURE WHAT TO DO HERE
        last_getitem_index = metacls.namespace_stack[-1].last_getitem_index
        for expr in last_getitem_index:
            if inspect.isgenerator(expr):
                for x in expr:
                    pass
        PurpleHierarchicalMetaClass.last_getitem_index = ()
