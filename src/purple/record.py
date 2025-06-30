'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple transient types with defined content and type protection

'''

from . import common, metaclass, static_record, clock


class Record(common.PurpleComponent, metaclass = metaclass.PurpleHierarchicalMetaClass):
    def __init__(self, **changes):
        ''' initialises a new (empty) transient record object

        a full hierarchical object is always created, but it is possible that parts of it
            are shallow copies of (references to) other transient record objects

        initialisation depends on
            class initial-value-dict, created at declaration
            a dictionary of overrides (changes)

        calls the classmethod _dp_transient_init for every state element declared in the Record subclass
        '''
        defaults = changes.pop('_dp_copyfrom', self._dp_initial_value)
        for state_element_name,state_element_type in self._dp_state_types.items():
            element_changes = changes.pop(state_element_name, common.UniqueObject)
            default = defaults[state_element_name]
            value = state_element_type._dp_transient_init(default, element_changes, self, state_element_name)
            self._dp_raw_setattr(state_element_name, value)
        assert not changes, 'record initialisation has invalid changes'

    @classmethod
    def _dp_transient_init(cls, default, changes, owner, name):
        '''called by Record() when creating a new transient containing a state element of type cls

        if this method is called, cls is a record subclass and default is a dict
        leaf and union state elements have their own implementation of dp-transient-init

        changes is one of
            an object of type cls
                return it (shallow copy)
            a dict
                apply changes sparsely to copy of default
            UniqueObject (means no changes)
                same as dict but ultimate in sparseness
            UnDefined
                copy default replacing everything with undef
        '''
        freeze_records = isinstance(owner, FrozenRecord)

        if isinstance(changes, cls):
            return changes.freeze() if freeze_records else changes

        if changes is common.UniqueObject:
            changes = {}
        elif changes is common.UnDefined:
            changes = {n:changes for n in cls._dp_state_types}
        assert isinstance(changes, dict)

        tcls = FrozenRecord.make_class(cls) if freeze_records else cls
        return tcls(_dp_copyfrom = default, **changes)

    def update(self, **changes):
        '''in-place modification with values replacing named elements of self

        if changes contains a record object, this is shallow-copied not hierarchically merged
        but if it contains a hierarchical dict, this does sparse changes in sub-records
        '''
        self._dp_transient_update(None, '', self, changes)

    def copy(self):
        return type(self)(**{k:self._dp_raw_getattr(k) for k in self._dp_state_types})

    def deep_copy(self):
        return self._dp_transient_deep_copy(self)

    def freeze(self):
        frozen_class = FrozenRecord.make_class(type(self))
        return frozen_class._dp_transient_deep_copy(self)

    @classmethod
    def _dp_transient_deep_copy(cls, self):
        return cls(**{
            k:c._dp_transient_deep_copy(self._dp_raw_getattr(k))
            for k,c in cls._dp_state_types.items()
        })

    @classmethod
    def _dp_transient_update(cls, owner, name_in_owner, self, changes):
        if isinstance(changes, dict):
            # hierarchical in-place update
            for attr_name,value in changes.items():
                attr_type = cls._dp_state_types[attr_name]
                attr = self._dp_raw_getattr(attr_name)
                attr_type._dp_transient_update(self, attr_name, attr, value)
        else:
            # shallow copy
            setattr(owner, name_in_owner, changes)

    def __setattr__(self, attr_name, value):
        try:
            state_type = self._dp_state_types[attr_name]
            state_type._dp_transient_setattr(self, attr_name, value)
        except KeyError:
            assert False, f'attempt to set a non-declared attribute, {attr_name}'

    @classmethod
    def _dp_elaborate(cls, name, top_component, instantiating_component, hierarchical_name, initial_value_dict):
        instance = static_record.StaticRecord.make_class(cls)(is_top = False)
        instantiating_component._dp_raw_setattr(name, instance)
        instance._dp_raw_setattr('name', (*hierarchical_name, name))
        instance._dp_raw_setattr('_dp_top_component', top_component)
        instance._dp_raw_setattr('_dp_union_instances', dict())
        instance._dp_raw_setattr('_dp_clocks', dict())
        return instance._dp_elaborate_substate(initial_value_dict)

    @classmethod
    def _dp_transient_setattr(cls, owner, name, value):
        if value is common.UnDefined:
            value = cls(**{n:value for n in cls._dp_state_types})
        assert owner._dp_state_types[name]._dp_class_matches(cls)
        owner._dp_raw_setattr(name, value)

    @classmethod
    def _dp_instance_setattr_leaf_changes(cls, owner, name, instance, value):
        static_cls = static_record.StaticRecord.make_class(cls)
        return static_cls._dp_instance_setattr_leaf_changes(owner, name, instance, value)

    @classmethod
    def _dp_instance_update_leaf_changes(cls, owner, name, self, values):
        static_cls = static_record.StaticRecord.make_class(cls)
        return static_cls._dp_instance_update_leaf_changes(owner, name, self, values)

    @classmethod
    def _dp_all_possible_values(cls):
        '''generator function producing all possible values for the Record
        '''
        for dict_value in cls._dp_all_possible_values_recursive(list(cls._dp_state_types)):
            yield cls(**dict_value)

    @classmethod
    def _dp_all_possible_values_recursive(cls, state_names):
        if not state_names:
            yield dict()
        else:
            first,others = state_names[0], state_names[1:]
            first_state_cls = cls._dp_state_types[first]
            for first_value in first_state_cls._dp_all_possible_values():
                first_dict = {first:first_value}
                for others_dict in cls._dp_all_possible_values_recursive(others):
                    yield dict(**first_dict, **others_dict)

    @classmethod
    def add_dp_clocks_from_base(cls, base):
        ''' called on declaration of a Record subclass, once for every base
        '''
        assert not base._dp_clock_declarations, f'clocks only possible in Model subclass, not {cls}'

    @classmethod
    def add_dp_clocks_from_annotations(cls):
        ''' called on declaration of a Record subclass
        '''
        if any(isinstance(v, clock.Clock) for v in cls.__annotations__.values()):
            assert False, f'clocks only possible in Model subclass, not {cls}'


class FrozenRecord(Record):
    _dp_class_cache = {}

    @classmethod
    def make_class(cls, cls_to_freeze):
        ''' convert a Record (transient) type to frozen variant
        '''
        # don't try to re-freeze a frozen class
        if issubclass(cls_to_freeze, FrozenRecord):
            record_cls = getattr(cls_to_freeze, '_dp_record_class', None)
            if record_cls is None:
                return cls_to_freeze
        else:
            record_cls = cls_to_freeze

        try:
            return cls._dp_class_cache[record_cls]

        except KeyError:
            # construct a new type
            classname = record_cls.__name__ + 'Frozen'
            bases = cls, record_cls
            namespace = type(cls).__prepare__(classname, bases)
            frozen_cls = type(cls)(classname, bases, namespace)

            frozen_cls._dp_record_class = record_cls
            cls._dp_class_cache[record_cls] = frozen_cls
            return frozen_cls

    @classmethod
    def _dp_frozen_catch(cls):
        assert False, 'attempt to modify a frozen Record'

    def __setattr__(self, attr_name, value):
        self._dp_frozen_catch()

    @classmethod
    def _dp_transient_update(cls, owner, name_in_owner, self, changes):
        cls._dp_frozen_catch()

    def melt(self):
        record_cls = getattr(self, '_dp_record_class', None)
        assert record_cls is not None, 'can only melt a class derived from a non-frozen one'
        return record_cls._dp_transient_deep_copy(self)

    def freeze(self):
        return self
