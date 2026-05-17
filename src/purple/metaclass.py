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

    or to something not-yet defined

    if we refer to a previously-declared sub-component, we need to be able to get a
    similar reference for its internal sub-state
    '''
    # PY-3-14
    # will not be triggered for an annotation
    # still needed for
    #   standalone (not using _ and []) bindings x.in << y.out
    #   initial values using _

    def __init__(self, name, purple_type, hierarchical_name):
        self.name = (*hierarchical_name, name)
        self.purple_type = purple_type
        PurpleHierarchicalMetaClass.add_type_proxy(self)

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

    not allowed to refer to a hierarchical component before it is declared
    # PY-3-14 can we remove this restriction?

    Port-to-handler binding
        could be for input port to call when a value arrives (push)
        could be for output port to call whan a value requested (pull)
        done by overriding shift on the class or on a reference to a prior annotation
            x: myPort >> handler_method_name
            y: myPort
            y >> other_handler_name
    '''
    # FIXME may need to search ambiguous-references to make names from global objects
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


class PurpleNamespace(dict):
    '''modified namespace dict allowing interception of object declaration

    unknown names may occur outside type annotations
        as binding targets
        in initial-value expressions

    may want to detect some names as magic methods eg "add_state_by_name"
    '''
    def __init__(self, caller_frame):
        super().__init__()
        self.caller_locals = caller_frame.f_locals
        self.caller_globals = caller_frame.f_globals
        if self.caller_globals is self.caller_locals:
            self.caller_globals = dict()
        self.ambiguous_references = dict()
        self.bindings = []
        self.last_getitem_index = ()
        self.recent_type_proxies = []

    def XXX__getitem__(self, key):
        unique_object = common.UniqueObject

        # maximum priority
        # "_" always gives a new type-proxy
        if key == '_':
            return PurpleTypeProxy(key, unique_object, ())

        # first priority:
        # references to annotations get a proxy, ignoring any default value that may have been set
        ### PY-3-14 not possible any more
#        v = self.annotations.get(key, unique_object)
#        if v is not unique_object:
#            return PurpleTypeProxy(key, v, ())

        # second priority:
        # if not an annotation value, return a normal local variable
        v = self.get(key, unique_object)
        if v is not unique_object:
            return v

        # third, fourth priority:
        # globals and builtins are returned unchanged, but remembered
        for ns in (self.caller_locals, self.caller_globals, __builtins__):
            v = ns.get(key, unique_object)
            if v is not unique_object:
                self.ambiguous_references[key] = PurpleTypeProxy(key, v, ())
                return v

        # finally, anything else is just remembered
        # FIXME: may need to convert this into a TypeProxy if annotation ongoing?
        #   would get a unique-object in the AR then a failed attribute lookup
        #   so remember all those attribute lookups as a chain of names in the AR?
        v = PurpleTypeProxy(key, unique_object, ())
        self.ambiguous_references[key] = v
        return v


def add_state(name, cls, default = common.UniqueObject):
    ns = PurpleHierarchicalMetaClass.namespace_stack[-1]
    ns.annotations[name] = cls
    if default is not common.UniqueObject:
        ns[name] = default


class PurpleHierarchicalMetaClass(PurpleComponentMetaClass):
    '''
    metaclass abuses the Python type annotation syntax to support declaration of the following
    - model/record internal state hierarchy
    - internal state initial values
    - rules for internal state modification
    - binding of ports and port-handlers

    namespace-stack allows nested class declaration

    metaclass supports deriving subclasses and overriding declarations from the base class(es)
    '''
    namespace_stack = []

    @classmethod
    def __prepare__(metacls, name, bases):
        caller = inspect.stack()[1].frame
        ns = PurpleNamespace(caller)
        metacls.namespace_stack.append(ns)
        return ns

    def __new__(metacls, name, bases, classdict):
        assert metacls.namespace_stack[-1] is classdict

        # PY-3-14
        print('+++++++++++++++++++++++++++++++++++++++')
        print(' making a hierarchical class', name)

        print(' get_annotations from namespace')
        print(annotationlib.get_annotate_from_class_namespace(classdict))

        cls = type.__new__(metacls, name, bases, classdict)

#        print(' legacy __annotations__')
#        print(cls.__annotations__)

        print(' get_annotations STRING')
        print(annotationlib.get_annotations(cls, format = annotationlib.Format.STRING))

#        print(' get_annotations VALUE')
#        print(annotationlib.get_annotations(cls, format = annotationlib.Format.VALUE))

        print(' get_annotations FWDREF')
        print(annotationlib.get_annotations(cls, format = annotationlib.Format.FORWARDREF))

        if name == 'SmokeTest':
            print('ttt =', getattr(cls, 'ttt', None))
            # delattr(cls, 'counter')

            print(' get_annotations FWDREF 2')
            f = annotationlib.get_annotations(cls, format = annotationlib.Format.FORWARDREF)
            print(f)
            print(' evaluating rules')
            print([(r.evaluate() if isinstance(r, annotationlib.ForwardRef) else r) for r in f['rules']])

            for k,v in f.items():
                print(k)
                if isinstance(v, annotationlib.ForwardRef):
                    class TTT:
                        port = 10
                    class COUNTER:
                        port = 20
                    cls._ = TTT
                    cls.counter = COUNTER
                    print(v.evaluate())

        fra = annotationlib.get_annotations(cls, format = annotationlib.Format.FORWARDREF)
        cls.__annotations__ = dict()
        for k,v in fra.items():
            print('  annotation', k)
            if isinstance(v, list):
                vv = [(r.evaluate() if isinstance(r, annotationlib.ForwardRef) else r) for r in v]
            elif isinstance(v, annotationlib.ForwardRef):
                vv = v.evaluate()
            else:
                vv = v
            cls.__annotations__[k] = vv

        ''' annotations as string is a dict of strings
            but it does not include the initial-value
            annotations as forwardref is empty
            annotations as value is empty
            get_annotate_from_class_namespace() seems to return nothing

            - how do I evaluate the strings in the declarers context?
            - I still need a namespace class for lazy evaluation of _ in initial values
            - problem: if a binding refers to an annotation (a state element)
                how do we distinguish this from a global with the same name?
                we don't know the annotations yet, when standalone bindings are declared
                    store it as a proxy
                    evaluate it at the end when annotations are known
                    may struggle to support arbitrary expressions in bindings?
                    maybe get_annotate_from_class_namespace() will work during?
            - how do we declare state with string name?
                maybe use the namespace to detect a reserved word
                Array[] uses this
            - cannot put f-strings in annotations (minor annoyance for rules)
            - cannot put and/or/if-else in annotations

            both FORWARDREF and VALUE can find members of the class (eg rule methods)
            well this was true but not any more
            seems that it depends on other annotations, unclear if trustworthy

            both FORWARDREF and VALUE may evaluate using initial values, which is a problem
            so need to remove these before calling?
            yes this works, FORWARDREF reverts to variable name

            evaluating FORWARDREF is a bit of a pain, because it may partially do it
            eg create a list of FORWARDREF

            can set class variables and FORWARDREF.eval() will pick these up

            do I need my namespace class any more?
            maybe I outlaw _ in initial values?
                probably there are alternatives
            maybe gets rid of the namespace stack too?
                maybe not; needed for bindings and maybe for create-state-from-string-name

            above is working for SmokeTest, Bomb, Record, Modulo (fails for Port)
                keeps namespace, but only because I need a place for bindings
                converts __annotations__, only because downstream functions not yet modified
        '''

        cls._dp_state_types = dict()
        cls._dp_initial_value = dict()
        cls._dp_rule_names = set()
        cls._dp_bindings = list()
        cls._dp_clock_declarations = dict()

        # get state, etc from all base classes in reverse order so that
        # more recent overrides older in the base class list
        for base in reversed(bases):
            if isinstance(base, metacls):
                cls._dp_add_state_from_base(base)
                cls._dp_add_rules_from_base(base, PurpleTypeProxy)
                cls._dp_add_bindings_from_base(base, classdict.bindings)
                cls._dp_add_clocks_from_base(base)

        # get new state from this class's annotation hints
        cls._dp_add_state_from_annotations()
        cls._dp_add_rules_from_annotations(PurpleTypeProxy)
        cls._dp_add_bindings_from_annotations(classdict.bindings)
        cls._dp_add_clocks_from_annotations()

        # now do the initial-values, later so that type changes are visible to bases
        for base in reversed(bases):
            if isinstance(base, metacls):
                cls.update_dp_initial_value_from_base(base)

        cls.update_dp_initial_value_from_base(cls)

        # hook for classes to do things when instantiated (eg port type checking)
        for state_element_name,state_element_type in cls._dp_state_types.items():
            state_element_type._dp_on_instantiation(cls, state_element_name)

        metacls.namespace_stack.pop()
        return cls

    def __getitem__(cls, index):
        '''used to add extra info on declaration, eg a set of port bindings

        and allows the bindings to be abbreviated
        (declaration name can be replaced by "_")

        records any generator expressions so that they can be iterated out as soon as
        the annotation is known
        '''
        if not isinstance(index, tuple):
            index = (index,)
        PurpleHierarchicalMetaClass.namespace_stack[-1].last_getitem_index = index
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
        metacls.namespace_stack[-1].bindings.append(binding)

    @classmethod
    def add_type_proxy(metacls, type_proxy):
        metacls.namespace_stack[-1].recent_type_proxies.append(type_proxy)

    @classmethod
    def resolve_bindings(metacls, forename, purple_type):
        '''called when an annotation is added and its name becomes known
        '''
        # add the name and type of the new annotation to all type-proxies
        recent_proxies = metacls.namespace_stack[-1].recent_type_proxies
        while recent_proxies:
            recent_proxies.pop().resolve(forename, purple_type)

        # fix any direct-to-port bindings
        current_bindings = metacls.namespace_stack[-1].bindings
        for b in current_bindings:
            b.resolve(forename, purple_type)

        # explode all binding-generators
        last_getitem_index = metacls.namespace_stack[-1].last_getitem_index
        for expr in last_getitem_index:
            if inspect.isgenerator(expr):
                for x in expr:
                    pass
        PurpleHierarchicalMetaClass.last_getitem_index = ()
