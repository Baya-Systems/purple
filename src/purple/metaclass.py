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
    ''' returned when a class declaration includes a reference to a declared sub-component (annotation)

    for use in lazily-evaluated expressions eg bindings and rule lists

    if we refer to a previously-declared sub-component, we need to be able to get a
    similar reference for its internal sub-state
    '''
    # FIXME unclear if this class is even needed any more as Binding is absorbing everything
    # possibly forward-refs to rules/clocks in abstract base classes?
    # OK obviously needed for port-to-port binding eval but most of the methods seem redundant?
    def __init__(self, name, purple_type, hierarchical_name):
        self.name = (*hierarchical_name, name)
        self.purple_type = purple_type

    def LEGACYresolve(self, discovered_forename, top_purple_type):
        # FIXME IS THIS CALLED ANY MORE?
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
        # FIXME DOES THIS EVER GET CALLED NOW WHEN THERE IS A PURPLE TYPE
        # OR ONLY FOR RAW NAMES?
        # FIXME IF WE CAN FIND THE TYPE FROM raw-annotations WE CAN DO BETTER
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
    def __init__(self, lhs, rhs, left2right):
        print('BINDING INIT')
        if not MetaClassState.peek().enable_binding_capture:
            raise NameError('binding capture not enabled')
        self.lhs = lhs # always a proxy object
        self.rhs = rhs # may be a proxy object or a function object (local method)
        self.left2right = left2right
        print('--add--binding', MetaClassState.peek().raw_bindings, self.lhs, '<>', self.rhs)
        MetaClassState.add_binding(self)
        print('   --add-binding-done')

    def resolve(self, discovered_forename, purple_type):
        # need to convert to names for which we need to replace a type/function with a proxy
        if self.lhs is purple_type:
            self.lhs = PurpleTypeProxy(discovered_forename, purple_type, ())
        if inspect.isfunction(self.rhs):
            self.rhs = PurpleTypeProxy(self.rhs.__name__, None, ())
        print('RESOLVE', self.lhs.name, self.rhs.name, self.left2right)

    def LEGACYconvert_to_names(self):
        if inspect.isfunction(self.rhs):
            self.rhs = PurpleTypeProxy(self.rhs.__name__, None, ())
        assert hasattr(self.lhs, 'name'), self.lhs
        assert self.lhs.name[0] != '_' and self.rhs.name[0] != '_'
        return self

    def __str__(self):
        lhs = '.'.join(self.lhs.name)
        rhs = '.'.join([self.rhs.__name__] if inspect.isfunction(self.rhs) else self.rhs.name)
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
        current_dp_cls = MetaClassState.peek().namespace
        current_dp_cls['_dp_addtostate_classes'].append(cls)

    cls_variables['adapt_name'] = classmethod(default_nameconv)
    cls_variables['__init_subclass__'] = classmethod(init_subclass)
    return ATSMetaClass('PurpleAddToState', tuple(), cls_variables)


# cannot use class variable, because they can be trashed by get_annotations()
MetaClassStateStack = []

class MetaClassState:
    '''
    namespace_stack is used by AddToState to record inner class declarations
    raw_bindings is used by Binding expressions to record themselves during __new__()
    and new_bindings because we need to replace "_" with the actual annotation name

    need a stack because of nested class declarations and also because of
    generic class creation during annotation evaluation
    '''
    # FIXME we may be adding the same binding multiple times as
    # we re-evaluate annotations
    @classmethod
    def push(cls, namespace):
        self = cls()
        self.namespace = namespace
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
        print('GetAnn', len(MetaClassStateStack))
        rv = annotationlib.get_annotations(target, format = format)
        print('   GetAnn', len(MetaClassStateStack))
        return rv

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
        print('INADDBINGIN', state.new_bindings, state.enable_binding_capture)
        if state.enable_binding_capture:
            MetaClassState.peek().new_bindings.append(binding)
        else:
            # force creation of a ForwardRef that we can re-evaluate with capture enabled
            # thus allowing replacement of "_" and [Port] classes in after-annotations
            raise NameError('binding capture not enabled')
        print('    INADDBINGIN')


def eval_string_annotation(ann_str: str, owner):
    ''' evaluate a STRING-format annotation with exactly the same context that FORWARDREF would use

    (Claude generated, only works for classes)
    needed because FORWARDREF ignores class-getitem or metaclass-getitem
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
        ns = super().__prepare__(name, bases)
        ns['_dp_addtostate_classes'] = []
        MetaClassState.push(ns)
        print('---' * (1 + len(MetaClassStateStack)), 'PUSH', name, MetaClassStateStack)
        return ns

    def __new__(metacls, name, bases, classdict):
        print('NEW CLS', name)
        dbgname = 'Fabric'
        mc_state = MetaClassState.peek()
        assert mc_state.namespace is classdict
        cls = type.__new__(metacls, name, bases, classdict)
        if name == dbgname: print('  ', name, 'NEWmade cls', metacls)
        unique_obj = common.UniqueObject

        # capture raw initial values, which are evaluated on the fly by python,
        # and replace with Proxy objects for binding evaluation
        if name == dbgname: print('  ', name, 'NEW A A', mc_state.raw_bindings, mc_state.enable_binding_capture)

        # CPython bug: https://github.com/python/cpython/issues/138425
        # if we use Format.VALUE or Format.FORWARDREF, it just assumes MyClass[a << b]
        # returns MyClass; a<<b is not evaluated

        if '_' in vars(cls):
            delattr(cls, '_')
        cls_annotations = MetaClassState.get_annotations(cls, annotationlib.Format.STRING)
        if name == dbgname: print('  ', name, 'NEW A B', mc_state.raw_bindings)
        if name == dbgname: print('  ', name, 'NEW A B', cls_annotations)
        raw_initial_value = dict()
        for n in cls_annotations:
            raw_initial_value[n] = getattr(cls, n, unique_obj)
            setattr(cls, n, PurpleTypeProxy(n, unique_obj, ()))
        if name == dbgname: print('  ', name, 'NEW B', mc_state.raw_bindings)

        # and for addtostate nested classes
        for ats_class in cls._dp_addtostate_classes:
            if hasattr(ats_class, '_'):
                delattr(ats_class, '_')
            ats_annotations = MetaClassState.get_annotations(ats_class, annotationlib.Format.STRING)

            for n in ats_annotations:
                name_in_cls = ats_class.adapt_name(n)
                raw_initial_value[name_in_cls] = getattr(ats_class, n, unique_obj)

            for n in cls_annotations:
                setattr(ats_class, n, PurpleTypeProxy(n, unique_obj, ()))

            for n in ats_annotations:
                cls_proxy = PurpleTypeProxy(name_in_cls, unique_obj, ())
                setattr(cls, name_in_cls, cls_proxy)
                setattr(ats_class, name_in_cls, cls_proxy)

        # FIXME
        # problem here? want to preserve non-Purple type annotations
        # and non-Purple class variables
        # so if any annotation resolves to something that isn't a Purple Model then don't replace it

        # state elements in base classes already have proxies which are visible to lazy evaluation
        # but the new cls may override an initial value by just setting a class variable
        # without a type annotation, so check for that
        if name == dbgname: print('  ', name, 'NEW C', mc_state.raw_bindings)
        for base in bases:
            # order of bases does not matter; we just need all the hierarchical state names
            if isinstance(base, metacls):
                for n in base._dp_state_types:
                    if n not in raw_initial_value:
                        iv = getattr(cls, n, unique_obj)
                        if (iv is not unique_obj) and (not isinstance(iv, PurpleTypeProxy)):
                            raw_initial_value[n] = iv

        # now evaluate the class annotations properly
        if name == dbgname: print('  ', name, 'NEW D', mc_state.raw_bindings)
        def re_eval(annot_name, annot_str, annot_class):
            annot_class._ = PurpleTypeProxy(annot_name, unique_obj, ())
            if annot_name == 'targets_to_bridge':
                print('AAAAAAA  EVAL', annot_str)
                print('AAAAAAA  EVAL', cls.RespPortArray, cls._, cls.tb_binder, cls.resp_to_bridge)
            annot = eval_string_annotation(annot_str, annot_class)

            if isinstance(annot, annotationlib.ForwardRef):
                rv = annot.evaluate(format = annotationlib.Format.STRING)
                assert '__annotationlib_name_' not in rv
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

        if name == dbgname: print('  ', name, 'NEW re-evaluate', mc_state.raw_bindings)
        mc_state.enable_binding_capture = True
        raw_annotations = {n:re_eval(n, a, cls) for n,a in cls_annotations.items()}
        if name == dbgname: print('  ', name, 'NEW re-evaluation complete', mc_state.raw_bindings)

        # and evaluate within addtostate nested classes
        for ats_class in cls._dp_addtostate_classes:
            mc_state.enable_binding_capture = False
            if '_' in vars(ats_class):
                delattr(ats_class, '_')
            ats_annotations = MetaClassState.get_annotations(ats_class, annotationlib.Format.STRING)
            mc_state.enable_binding_capture = True
            raw_annotations |= {
                ats_class.adapt_name(n):re_eval(n, a, ats_class) for n,a in ats_annotations.items()
            }
        if name == dbgname: print('  ', name, 'NEW added addtostate', mc_state.raw_bindings)

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
        if name == dbgname: print('  ', name, 'NEW added from base', mc_state.raw_bindings)

        # get new state from this class's annotation hints
        cls._dp_add_state_from_annotations(raw_annotations)
        cls._dp_add_rules_from_annotations(PurpleTypeProxy, raw_annotations)
        cls._dp_add_bindings_from_annotations(mc_state.raw_bindings)
        cls._dp_add_clocks_from_annotations(raw_annotations)
        if name == dbgname: print('  ', name, 'NEW added from annots')

        # now do the initial-values, later so that type changes are visible to bases
        for base in reversed(bases):
            if isinstance(base, metacls):
                cls.update_dp_initial_value_from_base(base, raw_initial_value)
        cls.update_dp_initial_value_from_base(cls, raw_initial_value)

        # hook for classes to do things when instantiated (eg port type checking)
        for state_element_name,state_element_type in cls._dp_state_types.items():
            state_element_type._dp_on_instantiation(cls, state_element_name)

        print('---' * (1 + len(MetaClassStateStack)), 'POP', name, MetaClassStateStack)
        for b in cls._dp_bindings:
            print('              ', str(b))
        mc_state.pop()
        if name == dbgname: print('  ', name, 'NEW done and returning', mc_state.raw_bindings, cls._dp_bindings)
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
        print('RSHIFT')
        'used to bind a port to a local port-handler function'
        Binding(cls, handler_name, True)
        return cls

    def __lshift__(cls, handler_name):
        print('LSHIFT')
        'used to bind a port to a local port-handler function'
        Binding(cls, handler_name, False)
        return cls

    @classmethod
    def REDUNDANTresolve_bindings(metacls, forename, purple_type):
        '''called when an annotation is added and its name becomes known
        '''
        # fix any direct-to-port bindings
        for b in mc_state.raw_bindings:
            b.resolve(forename, purple_type)

        # explode all binding-generators
        # FIXME NOT SURE WHAT TO DO HERE
        last_getitem_index = MetaClassState.peek().namespace.last_getitem_index
        for expr in last_getitem_index:
            if inspect.isgenerator(expr):
                for x in expr:
                    pass
        PurpleHierarchicalMetaClass.last_getitem_index = ()
