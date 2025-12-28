'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

constant (singleton) objects used in Purple

exception classes

base class for purple components with any methods that are shared eg by Model and Record
'''

import inspect


class FixedConstant:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

UniqueObject = FixedConstant('UniqueObject')
UnDefined = FixedConstant('UnDefined')
UnSelected = FixedConstant('UnSelected')


class PurpleException(Exception):
    @classmethod
    def insist(cls, condition, *args):
        if not condition:
            raise cls(*args)

    @classmethod
    def subclass(cls, class_name):
        return type(cls)(class_name, (cls,), {})

ReadUnDefined = PurpleException.subclass('ReadUnDefined')
UnResolvableType = PurpleException.subclass('UnResolvableType')
UnBoundPort = PurpleException.subclass('UnBoundPort')
CastToLeafFailure = PurpleException.subclass('CastToLeafFailure')
GuardFailed = PurpleException.subclass('GuardFailed')


ComponentName = tuple[str]  ## FIXME


class PurpleComponent:
    '''base class used for detecting Purple classes

    also the place where functions common to Record and Model are placed
    '''
    def __init__(self, *args, **kwargs):
        assert False, 'attempt to create a base class object'

    def guard(self, condition, *args):
        if not condition:
            raise GuardFailed(*args)

    def print(self, *args, **kwargs):
        try:
            top = self._dp_top_component
        except AttributeError:
            print(*args, **kwargs)
        else:
            current_inv = top._dp_current_invocation
            current_inv.print(args, kwargs)

    def guards_limited_to_code_block(self, component = None):
       return LocalGuards_ContextManager(component or self)

    def __eq__(self, other):
        'other needs to be a Record/Model with the same hierarchical structure'
        try:
            assert len(other._dp_state_types) == len(self._dp_state_types)
            for state_element_name,state_element_type in self._dp_state_types.items():
                # recursively traverse the hierarchy
                mine = self._dp_raw_getattr(state_element_name)
                theirs = other._dp_raw_getattr(state_element_name)
                assert mine == theirs
        except (AssertionError, AttributeError):
            return False
        return True

    def _dp_raw_getattr(self, attr_name):
        'immediate get-attribute with checks bypassed'
        return object.__getattribute__(self, attr_name)

    def _dp_raw_setattr(self, attr_name, value):
        'immediate set-attribute with checks bypassed'
        object.__setattr__(self, attr_name, value)

    def __str__(self, state_element_name = None):
        'used by Model and Record: Leaf and Union objects never exist'
        if state_element_name:
            cls = type(self)
            default_stringifier = getattr(cls, '_dp_default_stringifier', str)
            overrides = getattr(cls, '_dp_stringifiers', {})
            stringifier = overrides.get(state_element_name, default_stringifier)
            return stringifier(self._dp_raw_getattr(state_element_name))
        else:
            attributes = (f'{n}={self.__str__(n)}' for n in self._dp_state_types)
            return f'{type(self).__name__}({", ".join(attributes)})'

    def _dp_hierarchical_str(self, show_unselected = False, indent = '    ', eq = ' ---  '):
        'print record or model current state one line per leaf element'
        lines = self._dp_hierarchical_lines(show_unselected, 0)
        lines = [[indent * x[0] + x[1], *x[2:]] for x in lines]
        max_name_width = max(len(x[0]) for x in lines)
        lines = [x if len(x) == 1 else [x[0].ljust(max_name_width), eq, x[1]] for x in lines]
        return '\n'.join(''.join(x) for x in lines)

    def _dp_hierarchical_lines(self, show_unselected, num_indents):
        lines = []
        for n,v in self._dp_state_types.items():
            if show_unselected and hasattr(v, '_dp_union_hierarchial_lines'):
                lines.extend(v._dp_union_hierarchial_lines(self, n, num_indents))
            else:
                try:
                    attribute = self._dp_raw_getattr(n)
                    hier_lines = attribute._dp_hierarchical_lines(show_unselected, num_indents + 1)
                    lines.append([num_indents, n])
                    lines.extend(hier_lines)
                except AttributeError:
                    lines.append([num_indents, n, self.__str__(n)])
        return lines

    @classmethod
    def _dp_class_matches(cls, other_cls):
        return cls == other_cls

    def __getattribute__(self, attr_name):
        value = object.__getattribute__(self, attr_name)
        if attr_name.startswith('_dp_'):
            # this test is to break infinite recursion
            return value
        else:
            try:
                state_type = self._dp_state_types[attr_name]
                full_name = getattr(self, 'name', ()) + (attr_name,)
                return state_type._dp_instance_checkattr(value, full_name)
            except KeyError:
                return value

    @classmethod
    def _dp_elaborate(cls,
        name, top_component, instantiating_component, hierarchical_name, initial_value
    ):
        assert False, 'abstract base method called; not a static-state class'

    @classmethod
    def _dp_instance_checkattr(cls, value, name = ()):
        ReadUnDefined.insist(value is not UnDefined, f'Error reading undefined attribute: {".".join(name)}')
        return value

    @classmethod
    def _dp_on_instantiation(cls, owner_class, name_in_owner):
        pass

    @classmethod
    def _dp_all_possible_values(cls):
        assert False, 'abstract base method called; not a class with finite possible values'

    @classmethod
    def _dp_bind_local_handler(cls, handler_name):
        assert False, 'abstract base method called; not a port-class'

    @classmethod
    def _dp_get_union_options(cls):
        'called when ORing together classes to create a Union'
        return [cls]

    @classmethod
    def _dp_merge_initial_value(cls, owner_initial_value, base_initial_value):
        ''' makes the initial values for an instance of cls in owner-cls

        this version is for Record and Model

        called repeatedly, for every base of the owner class where the instance is declared
            because each instance can override the initial values or even change the element type

        returns a Record transient object, which comes back as owner-initial-value
        base-initial-value may be
            if no overrides are given, unique-object
            if selective overrides are given, dict
            a new transient record object wholly replacing the owner-initial-value
            undef wholly replacing the owner-initial-value
        '''
        if owner_initial_value is UniqueObject:
            # first call on instantiation: set up base-initial-value by hierarchical deep-copy
            owner_initial_value = cls._dp_copy_initial_value(cls._dp_initial_value)

        if base_initial_value is UniqueObject:
            # no value provided, so use owner-initial-value unmodified
            base_initial_value = dict()
        elif base_initial_value is UnDefined:
            # user request to force all substate to Undefined
            base_initial_value = {n:UnDefined for n in cls._dp_state_types}
        elif base_initial_value is UnSelected:
            # union request to force all substate to Unselected
            base_initial_value = {n:UnSelected for n in cls._dp_state_types}
        elif isinstance(base_initial_value, cls):
            # transient object provided, so convert to dict and use for all substate
            base_initial_value = {n:base_initial_value._dp_raw_getattr(n) for n in cls._dp_state_types}
        else:
            # (partial) dict of directed modifications
            assert isinstance(base_initial_value, dict), 'instantiated records initial values must be dicts or records'

        for state_element_name,override in base_initial_value.items():
            state_type = cls._dp_state_types[state_element_name]
            current = owner_initial_value[state_element_name]
            merged_value = state_type._dp_merge_initial_value(current, override)
            owner_initial_value[state_element_name] = merged_value

        return owner_initial_value

    @classmethod
    def _dp_copy_initial_value(cls, source_dict):
        'used by Record and Model'
        rv = {}
        with ShareKeys(cls._dp_state_types, getattr(cls, '_dp_key_stack', [])) as items:
            for n,st in items:
                rv[n] = st._dp_copy_initial_value(source_dict[n])
            return rv

    @classmethod
    def _dp_add_state_from_base(cls, base):
        ''' called on declaration of a Model or Record subclass, once for every base

        bases have already been declared so they have clean _dp_state_types
        '''
        cls._dp_state_types.update(base._dp_state_types)

    @classmethod
    def _dp_add_state_from_annotations(cls):
        ''' called on declaration of a Model or Record subclass, after bases are incorporated
        '''
        for state_element_name,state_element_type in cls.__annotations__.items():
            if inspect.isclass(state_element_type) and issubclass(state_element_type, PurpleComponent):
                cls._dp_state_types[state_element_name] = state_element_type


    @classmethod
    def update_dp_initial_value_from_base(cls, base):
        ''' called on declaration of a Model or Record subclass, once for every base

        as we step through the base classes we collect overrides of initial values
        initial-value override can be hierarchical (a dict of dicts) if state is a Model or Record
        the state may have its own (ready-merged) hierarchical dict

        bases have already been declared so they have clean _dp_initial_values
        but if the state type got changed in the subclass, it will no longer match so discarded
        the state class may have its own (ready-merged) hierarchical dict
        '''
        with ShareKeys(base._dp_state_types, getattr(cls, '_dp_key_stack', [])) as base_state:
            for state_element_name,state_element_type in base_state:
                if state_element_type == cls._dp_state_types.get(state_element_name, UniqueObject):
                    if base is cls:
                        try:
                            base_initial_value = getattr(cls, state_element_name)
                            delattr(cls, state_element_name)
                        except AttributeError:
                            base_initial_value = UniqueObject
                    else:
                        base_initial_value = base._dp_initial_value[state_element_name]
                    current_initial_value = cls._dp_initial_value.get(state_element_name, UniqueObject)
                    cls._dp_initial_value[state_element_name] = state_element_type._dp_merge_initial_value(
                        current_initial_value, base_initial_value)

    @classmethod
    def _dp_add_rules_from_base(cls, base, typeproxy_class):
        ''' called on declaration of a Record subclass, once for every base
        '''
        if base._dp_rule_names:
            assert False, f'rules only possible in Model subclass, not {cls}'

    @classmethod
    def _dp_add_rules_from_annotations(cls, typeproxy_class):
        ''' called on declaration of a Record subclass, once for every base
        '''
        if 'rules' in cls.__annotations__ or 'non_rules' in cls.__annotations__:
            assert False, f'rules only possible in Model subclass, not {cls}'

    @classmethod
    def _dp_add_bindings_from_base(cls, base, raw_cls_bindings):
        ''' called on declaration of a Record subclass, once for every base
        '''
        assert not base._dp_bindings, f'bindings only possible in Model subclass, not {cls}'

    @classmethod
    def _dp_add_bindings_from_annotations(cls, raw_cls_bindings):
        ''' called on declaration of a Record subclass
        '''
        assert not cls._dp_bindings, f'bindings only possible in Model subclass, not {cls}'


class ShareKeys:
    'adds keys to a global stack during an iteration'
    def __init__(self, dict_to_traverse, key_stack):
        self.key_stack = key_stack
        self.dict_to_traverse = dict_to_traverse
        self.original_stack_depth = len(key_stack)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        while self.original_stack_depth < len(self.key_stack):
            self.key_stack.pop(-1)

    def __iter__(self):
        for key,value in self.dict_to_traverse.items():
            self.key_stack.append(key)
            yield key,value
            self.key_stack.pop(-1)


class LocalGuards_ContextManager:
    'allows a process to contain multiple code blocks that are independently guarded'
    def __init__(self, component):
        top = component._dp_top_component
        self.current_inv = top._dp_current_invocation

    def __enter__(self):
        self.state_changes_on_enter = self.current_inv.state_changes.copy()
        self.printout_on_enter = self.current_inv.printout.copy()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is GuardFailed:
            self.current_inv.revert_state()
            self.current_inv.state_changes = self.state_changes_on_enter
            self.current_inv.apply_state()
            self.current_inv.printout = self.printout_on_enter
            return True
